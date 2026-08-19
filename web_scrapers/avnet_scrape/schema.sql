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

    -- availability
    in_stock          boolean NOT NULL DEFAULT false,
    stock             bigint,
    qty_min           integer,
    qty_mult          integer,
    warehouse         text,
    packaging         text,
    erp_status        text,
    -- Not in the search API payload yet - filled from a separate source later.
    price             numeric(14, 4),
    -- "In stock" alone is misleading: 977 parts have less stock than their
    -- minimum order quantity, so they cannot actually be bought.
    buyable           boolean GENERATED ALWAYS AS
                          (stock IS NOT NULL AND qty_min IS NOT NULL
                           AND stock >= qty_min) STORED,

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
