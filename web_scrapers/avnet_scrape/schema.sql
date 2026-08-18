CREATE TABLE IF NOT EXISTS products (
    item_number TEXT PRIMARY KEY,
    manufacturer_part_number TEXT,
    manufacturer_name TEXT,
    category TEXT,
    data JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);

CREATE TABLE IF NOT EXISTS products_history (
    id BIGSERIAL PRIMARY KEY,
    item_number TEXT NOT NULL,
    manufacturer_part_number TEXT,
    manufacturer_name TEXT,
    category TEXT,
    data JSONB NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_history_item_number ON products_history (item_number);

-- Whenever an upsert actually changes a product's data, archive the row's previous
-- state before it's overwritten, so `products` stays "current only" while
-- `products_history` accumulates every superseded version.
CREATE OR REPLACE FUNCTION products_archive_on_change() RETURNS trigger AS $$
BEGIN
    IF OLD.data IS DISTINCT FROM NEW.data THEN
        INSERT INTO products_history (
            item_number, manufacturer_part_number, manufacturer_name, category, data, valid_from, valid_to
        )
        VALUES (
            OLD.item_number, OLD.manufacturer_part_number, OLD.manufacturer_name, OLD.category, OLD.data, OLD.updated_at, now()
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_products_archive ON products;
CREATE TRIGGER trg_products_archive
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION products_archive_on_change();
