{{
    config(
        materialized='incremental',
        unique_key=['extraction_date', 'url', 'mentioned_ticker'],
        tags=['mart']
    )
}}

WITH news AS (
    SELECT *
    FROM {{ ref('stg_news')}}
    {% if is_incremental() %}
    WHERE extraction_date > (SELECT max(extraction_date) FROM {{ this }})
    {% endif %}
),

most_active_stocks AS (
    SELECT 
        DISTINCT ticker
    FROM {{ ref('stg_most_active_stocks') }}
    WHERE date = CURRENT_DATE
),

final AS (
    SELECT
        *
    FROM news
    WHERE mentioned_ticker IN (SELECT ticker FROM most_active_stocks)
    AND time_published_date >= CURRENT_DATE - INTERVAL '7 days'
)

SELECT * FROM final