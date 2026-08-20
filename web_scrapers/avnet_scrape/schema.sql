-- Current state of every scraped part, one row per ItemNumber.
--
-- Everything worth querying is a real column; the leftovers of the API payload
-- stay in `raw` (with 100%-NULL fields, scope-wide constants, duplicated fields
-- and Avnet-internal paths already stripped out by db.clean_product).
-- `attrs` holds the Attributes array folded into {"name": "value"} - that alone
-- is ~57% of the raw payload, four times bigger than it needs to be.
CREATE TABLE IF NOT EXISTS products (
    -- keys. ItemNumber, ERPPartNumber and WCSPartNumber are each unique across
    -- the whole catalog; manufacturer+MPN is NOT (517 colliding groups).
    item_number       text PRIMARY KEY,
    erp_part_number   text NOT NULL UNIQUE,
    wcs_part_number   text,
    variant_number    text,

    -- manufacturer. The ERP/vendor variants really do diverge from the primary
    -- ones (11 394 / 3 868 / 5 734 rows), so all of them are kept.
    mfr_code          text NOT NULL,
    mfr_name          text NOT NULL,
    erp_mfr_code      text,
    erp_supplier_code text,
    mpn               text NOT NULL,
    erp_mfr_part      text,
    vendor_part       text,
    mpn_norm          text GENERATED ALWAYS AS
                          (upper(regexp_replace(mpn, '[^A-Za-z0-9]', '', 'g'))) STORED,

    -- category
    cat_l1            text NOT NULL,
    -- 1 462 of the 30 880 in-stock parts carry no Level_2_Name at all; only
    -- fetch_products' fallback to the requested category name hid that.
    cat_l2            text,
    cat_l3            text,
    cat_l4            text,
    sap_matgroup      text,

    -- availability. Only what the catalog asserts about a part; the numbers
    -- that move - quantity and price - live in products_stock / products_price,
    -- joined on item_number (see the products_live view at the bottom).
    -- in_stock is kept because it is what makes a part worth a live lookup.
    in_stock          boolean NOT NULL DEFAULT false,
    qty_min           integer,
    qty_mult          integer,
    warehouse         text,
    packaging         text,
    erp_status        text,

    -- lifecycle
    active_date       date,
    obsolete          boolean,
    eol               boolean,
    lifecycle_risk    text,
    supply_risk       text,
    env_risk          text,

    -- compliance
    rohs_code         text,      -- Y = RoHS 6, C = RoHS 10
    reach_compliant   boolean,
    hts_code          text,
    eccn_code         text,

    -- content
    short_description text,
    long_description  text,
    datasheet_url     text,
    ihs_datasheet_url text,

    -- attributes: {"Resistance": "10 kOhm", ...}
    attrs             jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- only for the 1.5% of attributes where MINVAL <> MAXVAL
    attr_ranges       jsonb,
    -- whatever is left of the payload
    raw               jsonb NOT NULL,

    -- sha256 over the payload; the upsert writes only when this changes, which
    -- is what keeps the table from bloating 38x like the previous one did.
    data_hash         bytea NOT NULL,
    first_seen_at     timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- for databases created before cat_l2 was allowed to be NULL
ALTER TABLE products ALTER COLUMN cat_l2 DROP NOT NULL;

-- for databases created while quantity and price still lived here. buyable goes
-- first because it is generated from stock; it comes back in products_live,
-- where it can finally be computed from the live quantity instead of the index's.
ALTER TABLE products DROP COLUMN IF EXISTS buyable;
ALTER TABLE products DROP COLUMN IF EXISTS stock;
ALTER TABLE products DROP COLUMN IF EXISTS price;

ALTER TABLE products SET (autovacuum_vacuum_scale_factor = 0.02);

CREATE INDEX IF NOT EXISTS idx_products_mfr_mpn      ON products (mfr_code, mpn_norm);
CREATE INDEX IF NOT EXISTS idx_products_category     ON products (cat_l1, cat_l2);
CREATE INDEX IF NOT EXISTS idx_products_erp_status   ON products (erp_status);
CREATE INDEX IF NOT EXISTS idx_products_in_stock     ON products (in_stock) WHERE in_stock;
CREATE INDEX IF NOT EXISTS idx_products_updated_at   ON products (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_products_attrs        ON products USING gin (attrs jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_products_search       ON products USING gin (
    to_tsvector('simple', coalesce(short_description, '') || ' ' || mpn));

-- "Still in the catalog as of" - written for every part on every run, whether
-- it changed or not, which is why it lives apart from the fat products rows:
-- those only fit 4 to a page, so an in-place update there could not stay HOT
-- and every run would rewrite the whole 57 MB heap. Here a page holds ~65 rows
-- with room to spare, so the touches stay HOT and the table stays flat. A part
-- missing from a run keeps its older last_seen_at, which is how delisted parts
-- are spotted.
CREATE TABLE IF NOT EXISTS products_seen (
    item_number  text PRIMARY KEY REFERENCES products (item_number) ON DELETE CASCADE,
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

-- fillfactor 50 leaves each page as many spare slots as it holds rows, so a
-- full run of ~29k touches fits without spilling onto new pages.
ALTER TABLE products_seen SET (fillfactor = 50, autovacuum_vacuum_scale_factor = 0.05);

-- Deliberately no index on last_seen_at: it is the only column that ever
-- changes, and indexing it would make every one of those updates non-HOT -
-- exactly what this table exists to avoid. Scanning a few MB to find stale
-- parts is cheaper than paying for that index on every run.
DROP INDEX IF EXISTS idx_products_seen_last_seen_at;

-- Superseded versions. The whole previous row is kept as one jsonb snapshot
-- instead of mirroring 40+ typed columns that would have to be kept in sync
-- with the table above forever.
CREATE TABLE IF NOT EXISTS products_history (
    id          bigserial PRIMARY KEY,
    item_number text NOT NULL,
    data_hash   bytea NOT NULL,
    snapshot    jsonb NOT NULL,
    valid_from  timestamptz NOT NULL,
    valid_to    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_history_item_number ON products_history (item_number, valid_to DESC);

-- Archive the previous state of a row before an upsert overwrites it, so
-- `products` stays current-only and `products_history` accumulates the rest.
-- Keyed off data_hash so that a price-only update does not fabricate a version.
CREATE OR REPLACE FUNCTION products_archive_on_change() RETURNS trigger AS $$
BEGIN
    IF OLD.data_hash IS DISTINCT FROM NEW.data_hash THEN
        INSERT INTO products_history (item_number, data_hash, snapshot, valid_from, valid_to)
        VALUES (OLD.item_number, OLD.data_hash, to_jsonb(OLD), OLD.updated_at, now());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_products_archive ON products;
CREATE TRIGGER trg_products_archive
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION products_archive_on_change();

-- Live availability, straight from SAP via the inventory endpoint. The search
-- API's `products.stock` is only correct at the moment the search index was
-- built: measured against this endpoint it is ~92% accurate a week after a
-- re-stamp and ~73% a month later, and ~3% of parts it calls in stock are
-- really at zero. So `products.stock` is what the catalog claims and this table
-- is what can actually be shipped.
--
-- Separate from `products` for the same reason products_seen is: this is
-- rewritten for every part on every run, and products rows are too fat to
-- update in place without rewriting the whole heap.
CREATE TABLE IF NOT EXISTS products_stock (
    item_number     text PRIMARY KEY REFERENCES products (item_number) ON DELETE CASCADE,
    qty             bigint,      -- getinventory.qas
    lead_time       text,        -- getinventory.plifz, e.g. "27 weeks"
    unit            text,        -- getinventory.meins, e.g. "ST"
    -- "27 weeks" -> 27. Leading digits only, so a "1-2 weeks" style value reads
    -- as its lower bound rather than as 12.
    lead_time_weeks integer GENERATED ALWAYS AS
                        ((substring(lead_time from '^\s*(\d+)'))::integer) STORED,
    checked_at      timestamptz NOT NULL DEFAULT now()
);

-- Same fillfactor bargain as products_seen: every row is touched every run, so
-- leave each page half empty and let the updates stay HOT.
ALTER TABLE products_stock SET (fillfactor = 50, autovacuum_vacuum_scale_factor = 0.05);

-- Deliberately no index on qty or checked_at - both change on every run, and
-- indexing either would make those updates non-HOT, which is exactly what this
-- table's shape exists to avoid.

-- Current price per part, filled by a source that does not exist yet: prices
-- are gated behind a signed-in Abacus account, and the anonymous session the
-- scraper uses fires no pricing call at all. The table and the `price` CLI mode
-- are here so that only scraper.fetch_price_chunk() has to be written once an
-- account is available.
--
-- `products.price` predates this table and stays NULL; this is the live one.
CREATE TABLE IF NOT EXISTS products_price (
    item_number text PRIMARY KEY REFERENCES products (item_number) ON DELETE CASCADE,
    price       numeric(14, 4),
    currency    text,
    -- distributor pricing is tiered, so keep room for the whole ladder:
    -- [{"qty": 1, "price": 0.42}, {"qty": 100, "price": 0.31}, ...]
    breaks      jsonb,
    checked_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE products_price SET (fillfactor = 50, autovacuum_vacuum_scale_factor = 0.05);

-- The one place that stitches the three tables together. Everything a buying
-- decision needs, with the live quantity rather than the catalog's claim - and
-- `buyable` computed the way it always should have been: against what can
-- actually be shipped, not against the index's month-old number.
--
-- Dropped and recreated rather than CREATE OR REPLACE so that adding a column
-- to `products` cannot leave the view stale or fail to replace.
DROP VIEW IF EXISTS products_live;
CREATE VIEW products_live AS
SELECT p.*,
       s.qty,
       s.lead_time,
       s.lead_time_weeks,
       s.unit,
       s.checked_at AS stock_checked_at,
       r.price,
       r.currency,
       r.breaks,
       r.checked_at AS price_checked_at,
       (s.qty IS NOT NULL AND p.qty_min IS NOT NULL AND s.qty >= p.qty_min) AS buyable
FROM products p
LEFT JOIN products_stock s USING (item_number)
LEFT JOIN products_price r USING (item_number);
