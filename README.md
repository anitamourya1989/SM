# SM
SELECT *
FROM stock_positions
WHERE gem = 1
  AND DATE(created_at) = CURRENT_DATE
ORDER BY down_52_high ASC;
