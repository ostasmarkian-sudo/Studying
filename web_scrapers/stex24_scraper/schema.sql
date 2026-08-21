-- Current state of the stex24 catalogue, one row per product.
--
-- Lives in the same product_avnet database as the Avnet and Automation24
-- tables, hence the prefixed name. It shares no keys with them: those are
-- keyed on item_number and article_id, this one on the shop's own uuid.
CREATE TABLE IF NOT EXISTS stex24_products (
    -- Shopware id, 32 hex characters, no dashes. It is the key well beyond this
    -- table: /detail/{uuid} redirects to the product page, and the Store API
    -- takes a list of these. That is why it is the PRIMARY KEY, not the sku.
    uuid          text PRIMARY KEY,

    -- The shop's article number ("103791"), also the tail of the SEO url.
    -- Unique in practice, but deliberately NOT declared UNIQUE: variants may
    -- share one, and a single violation would roll back an entire batch
    -- (a lesson already learned the hard way on avnet).
    sku           text,

    -- Nullable because the catalogue is filled in two passes: discover writes
    -- the uuid, the API pass fills everything below.
    name          text,
    brand         text,
    mpn           text,
    gtin          text,

    -- Two DIFFERENT prices, and they must not be conflated:
    --   price     - per single unit;
    --   price_min - the cheapest volume tier, i.e. the largest batch.
    price         numeric(12, 2),
    price_min     numeric(12, 2),
    price_is_from boolean NOT NULL DEFAULT false,
    currency      text,

    stock_state   text,

    -- Number of child variants; 0 for a product that has none.
    variants      smallint,

    -- The branches the product was found in. An array rather than one column:
    -- the same product sits in several categories, and a single column would
    -- depend on the order in which they happen to be walked.
    categories    text[] NOT NULL,

    -- Canonical SEO url. A link is always recoverable as
    -- https://stex24.com/detail/{uuid}, so that form is not stored separately.
    url           text,
    image         text,
    description   text,

    -- Fingerprint of exactly the fields stored here. It exists so updated_at
    -- moves only on a real change rather than on every run.
    data_hash     bytea NOT NULL,

    first_seen_at timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    -- Unlike updated_at this is rewritten every run: the gap between the two
    -- is what identifies a product that has dropped out of the catalogue.
    last_seen_at  timestamptz NOT NULL DEFAULT now()
);

-- last_seen_at is rewritten for every row on every run, so leave room on the
-- pages for HOT updates instead of letting the table sprawl each time.
ALTER TABLE stex24_products SET (fillfactor = 70);

CREATE INDEX IF NOT EXISTS idx_stex24_sku        ON stex24_products (sku);
CREATE INDEX IF NOT EXISTS idx_stex24_brand      ON stex24_products (brand);
CREATE INDEX IF NOT EXISTS idx_stex24_mpn        ON stex24_products (mpn);
CREATE INDEX IF NOT EXISTS idx_stex24_state      ON stex24_products (stock_state);
CREATE INDEX IF NOT EXISTS idx_stex24_updated_at ON stex24_products (updated_at DESC);
-- GIN, because categories is an array and the question asked of it is always
-- "which products are in branch X".
CREATE INDEX IF NOT EXISTS idx_stex24_categories ON stex24_products USING gin (categories);


-- Stock levels, one row per product. Kept apart from stex24_products because
-- quantities change constantly while a product card almost never does: merged
-- into one table, every refresh would rewrite ten thousand wide rows for the
-- sake of two numbers. The link back is the uuid.
CREATE TABLE IF NOT EXISTS stex24_stock (
    uuid          text PRIMARY KEY REFERENCES stex24_products (uuid) ON DELETE CASCADE,
    sku           text,

    -- The shop keeps goods in two warehouses and shows them separately:
    --   express  - "Dispatch today from Express warehouse", i.e. available now;
    --   external - "4 - 6 working days from external warehouse", i.e. later.
    -- The site only draws a column when the number is above zero, so 0 here
    -- means exactly what a missing column means: that warehouse is empty.
    -- external_qty, by contrast, can be NULL - the product simply has no
    -- mega_manufacturer_stock field, meaning no external warehouse is tracked.
    express_qty   integer,
    external_qty  integer,
    total_qty     integer,

    -- How much has already been ordered from the supplier.
    ordered_qty   integer,

    available     boolean,
    -- Lead time: "3-5 workdays" plus the bounds as numbers.
    delivery_time text,
    delivery_min  smallint,
    delivery_max  smallint,
    restock_time  smallint,

    data_hash     bytea NOT NULL,

    first_seen_at timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now()
);

-- HOT updates are this table's normal mode of operation, so leave more room
-- than in the catalogue: quantities are rewritten every run and rows are narrow.
ALTER TABLE stex24_stock SET (fillfactor = 60);

CREATE INDEX IF NOT EXISTS idx_stex24_stock_sku     ON stex24_stock (sku);
CREATE INDEX IF NOT EXISTS idx_stex24_stock_total   ON stex24_stock (total_qty DESC);
CREATE INDEX IF NOT EXISTS idx_stex24_stock_updated ON stex24_stock (updated_at DESC);


-- Migration for the move to the Store API. Nothing here drops data; the
-- statements are idempotent so init_db() can run them on every start.
ALTER TABLE stex24_products ALTER COLUMN sku  DROP NOT NULL;
ALTER TABLE stex24_products ALTER COLUMN name DROP NOT NULL;

-- The API returns the full volume discount grid instead of a "from EUR 0.55"
-- string:  [{"qty": 249, "price": 0.91}, ..., {"qty": null, "price": 0.55}]
-- qty is the upper bound of the bracket, null meaning "and beyond, no limit".
ALTER TABLE stex24_products ADD COLUMN IF NOT EXISTS price_tiers jsonb;

-- Many entries are variants of a shared parent. That used to be visible only
-- as "7 variations" in the markup; now it arrives as a real identifier.
ALTER TABLE stex24_products ADD COLUMN IF NOT EXISTS parent_uuid text;

CREATE INDEX IF NOT EXISTS idx_stex24_parent ON stex24_products (parent_uuid);

-- Superseded by the columns above, kept only so existing data is not lost:
--   price_display - the "from EUR 0.52" string scraped from the markup;
--   availability  - the schema.org value from the JSON-LD block.
-- Neither is written any more. Drop them once the API data has proven itself.
