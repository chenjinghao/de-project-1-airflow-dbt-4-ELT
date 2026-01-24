{{config(
    materialized='incremental'
)}}

WITH most_active_stocks AS (
    SELECT
        date,
        most_active
    FROM {{ source('stocks_db', 'raw_most_active_stocks') }}
    {% if is_incremental() %}
    WHERE date > (SELECT max(date) FROM {{ this }})
    {% endif %}
),

expanded AS (
    SELECT
        mas.date,
        elem AS obj
    FROM most_active_stocks mas
    CROSS JOIN jsonb_array_elements(COALESCE(mas.most_active::jsonb, '[]'::jsonb)) AS elem
),

converted_table AS (
    SELECT
        date,
        (obj->>'price')::numeric AS price,
        obj->>'ticker' AS ticker,
        (obj->>'volume')::bigint AS volume,
        (obj->>'change_amount')::numeric AS change_amount,
        REPLACE(obj->>'change_percentage', '%', '')::numeric AS change_percentage
    FROM expanded
),

ranked_by_date AS (
    SELECT
        date,
        ticker,
        price,
        volume,
        change_amount,
        change_percentage,
        ROW_NUMBER() OVER (PARTITION BY date ORDER BY volume DESC) AS rn
    FROM converted_table
),

final AS (
    SELECT
        date,
        ticker,
        price,
        volume,
        change_amount,
        change_percentage,
        rn
    FROM ranked_by_date
    WHERE rn <= 3
    ORDER BY volume DESC
)

SELECT * FROM final