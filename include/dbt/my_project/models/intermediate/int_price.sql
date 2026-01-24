{{
    config(
        materialized='incremental',
        unique_key=['extraction_date', 'symbol'],
        tags=['intermediate']
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
    SELECT DISTINCT
        extraction_date,
        symbol,
        ROUND(AVG(close_price) OVER (PARTITION BY symbol), 2) AS avg_close_price_past_100days,
        ROUND(MAX(high_price) OVER (PARTITION BY symbol), 2) AS max_price_past_100days,
        ROUND(MIN(low_price) OVER (PARTITION BY symbol), 2) AS min_price_past_100days,
        ROUND(AVG(volume) OVER (PARTITION BY symbol), 2) AS avg_volume_past_100days,
        ROUND(MAX(volume) OVER (PARTITION BY symbol), 2) AS max_volume_past_100days,
        ROUND(MIN(volume) OVER (PARTITION BY symbol), 2) AS min_volume_past_100days
    FROM price 
)

SELECT * FROM final