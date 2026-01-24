{{
config(
    materialized='table',
    tags=['mart']
)
}}

WITH price AS (
    SELECT *
    FROM {{ ref('stg_price')}}
),

final AS (
    SELECT
        extraction_date,
        symbol,
        price_date,
        ROUND(((close_price - open_price) / open_price) * 100, 3) AS pct_daily_change,
        COALESCE(volume - LAG(volume) OVER (ORDER BY price_date), 0::BIGINT) AS diff_vol
    FROM price
    ORDER BY price_date
)


SELECT * FROM final