-- Поточний стан каталогу Automation24, один рядок на товар.
--
-- Живе в тій самій БД product_avnet, що й таблиці Avnet, тому назва з префіксом:
-- ключі там свої (item_number), тут свій (article_id лістингу), спільного нічого.
--
-- Усе, що лістинг віддає в GA4-атрибутах, лежить окремими колонками - парсити
-- текст цін не доводиться, сервер сам віддає "47.60" машинним значенням.
CREATE TABLE IF NOT EXISTS automation24_products (
    -- data-article-id: внутрішній id, ним же лістинг зв'язує кошик і наявність.
    article_id    integer PRIMARY KEY,
    -- data-sku приходить як "103376;0" - артикул і номер варіанта.
    -- Навмисно НЕ UNIQUE: варіанти одного товару можуть ділити артикул, а одне
    -- порушення UNIQUE відкотило б увесь батч (на цьому вже обпікся avnet).
    sku           text NOT NULL,
    variant       smallint,

    name          text NOT NULL,
    brand         text,

    -- ціни нетто, без ПДВ. rrp є лише там, де є знижка (~50% товарів).
    price         numeric(12, 2),
    rrp           numeric(12, 2),
    discount      numeric(12, 2),
    currency      text,

    -- власна (листова) категорія товару, а не коренева гілка обходу: товар
    -- зустрічається в кількох гілках, і корінь залежав би від порядку обходу.
    category      text,
    category_id   integer,

    -- Розібраний текст наявності. Сирий текст лишається в availability, бо
    -- саме він робить класифікацію перевірюваною, якщо сайт додасть новий стан.
    --   in_stock   - "in stock"
    --   few        - "few in stock"
    --   reserve    - "currently out of stock - buy now and reserve"
    --   order_item - "Order item - will be ordered from the manufacturer"
    --   unavailable- "Not available"
    stock_state   text,
    -- "Dispatch next working day" -> 1, "Dispatch expected in 8 working days" -> 8
    dispatch_days smallint,
    availability  text,

    rating        numeric(3, 2),
    reviews       integer,

    url           text NOT NULL,
    image         text,
    description   text,

    -- Відбиток саме тих полів, які тут зберігаються. Потрібен, щоб updated_at
    -- рухався тільки від справжньої зміни, а не від кожного прогону.
    data_hash     bytea NOT NULL,

    first_seen_at timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    -- на відміну від updated_at, оновлюється щопрогону: різниця між ними і є
    -- ознакою товару, який зник з каталогу.
    last_seen_at  timestamptz NOT NULL DEFAULT now()
);

-- last_seen_at переписується для кожного рядка щопрогону, тож лишаємо на
-- сторінках місце під HOT-оновлення замість того, щоб щоразу розповзатися.
ALTER TABLE automation24_products SET (fillfactor = 70);

CREATE INDEX IF NOT EXISTS idx_a24_sku        ON automation24_products (sku);
CREATE INDEX IF NOT EXISTS idx_a24_brand      ON automation24_products (brand);
CREATE INDEX IF NOT EXISTS idx_a24_category   ON automation24_products (category_id);
CREATE INDEX IF NOT EXISTS idx_a24_state      ON automation24_products (stock_state);
CREATE INDEX IF NOT EXISTS idx_a24_updated_at ON automation24_products (updated_at DESC);
