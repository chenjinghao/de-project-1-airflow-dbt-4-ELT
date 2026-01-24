{{
config(
    materialized='incremental',
    unique_key=['extraction_date', 'symbol', 'price_date'],
    tags=['mart']
)
}}

WITH price AS (
    SELECT *
    FROM {{ ref('stg_price')}}
    {% if is_incremental() %}
    WHERE extraction_date > (SELECT max(extraction_date) FROM {{ this }})
    {% endif %}
),

final AS (
    SELECT
        extraction_date,
        symbol,
        price_date,
        ROUND(((close_price - open_price) / open_price) * 100, 3) AS pct_daily_change,
        COALESCE(volume - LAG(volume) OVER (PARTITION BY extraction_date, symbol ORDER BY price_date), 0::BIGINT) AS diff_vol
    FROM price
    ORDER BY price_date
)


SELECT * FROM final