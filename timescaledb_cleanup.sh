#!/bin/bash
# TimescaleDB unified_audit_logs 分批删除脚本
# 删除 2026-04-07 之前的数据（即 30 天前的数据）

CONTAINER="ontology-timescaledb"
DB="timescale_db"
USER="postgres"

echo "=== 开始分批删除 unified_audit_logs ==="

# 3月小数据量天
for date in 2026-03-11 2026-03-13 2026-03-14 2026-03-15 2026-03-16 2026-03-17 2026-03-18 2026-03-19 2026-03-20 2026-03-23 2026-03-24; do
    next_date=$(date -j -f "%Y-%m-%d" "$date" +"%Y-%m-%d" 2>/dev/null || date -d "$date" +"%Y-%m-%d" 2>/dev/null)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        next_date=$(date -v+1d -f "%Y-%m-%d" "$date" +"%Y-%m-%d")
    else
        next_date=$(date -d "$date + 1 day" +"%Y-%m-%d")
    fi
    echo "[$(date '+%H:%M:%S')] 删除 $date (~18万条) ..."
    docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '$date' AND timestamp < '$next_date';" &
    wait
done

# 3月25日
echo "[$(date '+%H:%M:%S')] 删除 2026-03-25 (~123万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-25' AND timestamp < '2026-03-26';" &
wait

# 3月26日 - 分两批（上下午）
echo "[$(date '+%H:%M:%S')] 删除 2026-03-26 上午 (~138万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-26' AND timestamp < '2026-03-26 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-03-26 下午 (~138万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-26 12:00' AND timestamp < '2026-03-27';" &
wait

# 3月27日 - 分两批
echo "[$(date '+%H:%M:%S')] 删除 2026-03-27 上午 (~118万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-27' AND timestamp < '2026-03-27 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-03-27 下午 (~118万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-27 12:00' AND timestamp < '2026-03-28';" &
wait

# 3月28日 - 分两批
echo "[$(date '+%H:%M:%S')] 删除 2026-03-28 上午 (~105万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-28' AND timestamp < '2026-03-28 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-03-28 下午 (~105万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-28 12:00' AND timestamp < '2026-03-29';" &
wait

# 3月30日
echo "[$(date '+%H:%M:%S')] 删除 2026-03-30 (~123万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-30' AND timestamp < '2026-03-31';" &
wait

# 3月31日 - 分两批
echo "[$(date '+%H:%M:%S')] 删除 2026-03-31 上午 (~84万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-31' AND timestamp < '2026-03-31 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-03-31 下午 (~84万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-03-31 12:00' AND timestamp < '2026-04-01';" &
wait

# 4月1日 - 分两批
echo "[$(date '+%H:%M:%S')] 删除 2026-04-01 上午 (~118万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-01' AND timestamp < '2026-04-01 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-04-01 下午 (~118万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-01 12:00' AND timestamp < '2026-04-02';" &
wait

# 4月2日 - 分两批
echo "[$(date '+%H:%M:%S')] 删除 2026-04-02 上午 (~189万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-02' AND timestamp < '2026-04-02 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-04-02 下午 (~189万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-02 12:00' AND timestamp < '2026-04-03';" &
wait

# 4月3日 - 分四批（数据量最大800万）
for slot in "2026-04-03 00:00" "2026-04-03 06:00" "2026-04-03 12:00" "2026-04-03 18:00"; do
    IFS=' ' read -r date time <<< "$slot"
    if [[ "$time" == "00:00" ]]; then
        next="${date} 06:00"
    elif [[ "$time" == "06:00" ]]; then
        next="${date} 12:00"
    elif [[ "$time" == "12:00" ]]; then
        next="${date} 18:00"
    else
        next="$(date -j -f "%Y-%m-%d %H:%M" "${date} 18:00" +"%Y-%m-%d %H:%M" 2>/dev/null || date -d "${date} 18:00 + 6 hour" +"%Y-%m-%d %H:%M")"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            next=$(date -v+6H -f "%Y-%m-%d %H:%M" "${date} 18:00" +"%Y-%m-%d %H:%M")
        else
            next=$(date -d "${date} 18:00 + 6 hour" +"%Y-%m-%d %H:%M")
        fi
    fi
    echo "[$(date '+%H:%M:%S')] 删除 ${date} ${time} ~ ${next} (~200万) ..."
    docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '${date} ${time}' AND timestamp < '${next}';" &
    wait
done

# 4月4日 - 分两批
echo "[$(date '+%H:%M:%S')] 删除 2026-04-04 上午 (~56万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-04' AND timestamp < '2026-04-04 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-04-04 下午 (~56万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-04 12:00' AND timestamp < '2026-04-05';" &
wait

# 4月5日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-05 上午 (~53万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-05' AND timestamp < '2026-04-05 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-04-05 下午 (~53万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-05 12:00' AND timestamp < '2026-04-06';" &
wait

# 4月6日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-06 上午 (~39万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-06' AND timestamp < '2026-04-06 12:00';" &
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-04-06 下午 (~39万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-06 12:00' AND timestamp < '2026-04-07';" &
wait

# 4月7日（只有1.6万，直接删）
echo "[$(date '+%H:%M:%S')] 删除 2026-04-07 (~1.6万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM unified_audit_logs WHERE timestamp >= '2026-04-07' AND timestamp < '2026-04-08';" &
wait

echo ""
echo "=== 删除完成，开始 VACUUM FULL ==="
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "VACUUM FULL unified_audit_logs;"

echo ""
echo "=== 清理完成，当前数据量 ==="
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "
SELECT COUNT(*) as remaining_rows, MIN(timestamp) as min_time, MAX(timestamp) as max_time FROM unified_audit_logs;
"

echo ""
echo "=========================================="
echo "=== time_series_data 清理（保留7天）==="
echo "=========================================="

# 4月7日~4月9日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-07 ~ 2026-04-10 (~103万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-07' AND timestamp < '2026-04-10';"
wait

# 4月10日~4月13日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-10 ~ 2026-04-13 (~64万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-10' AND timestamp < '2026-04-13';"
wait

# 4月13日~4月16日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-13 ~ 2026-04-16 (~51万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-13' AND timestamp < '2026-04-16';"
wait

# 4月16日~4月17日（89万）
echo "[$(date '+%H:%M:%S')] 删除 2026-04-16 ~ 2026-04-17 (~89万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-16' AND timestamp < '2026-04-17';"
wait

# 4月17日~4月18日（89万）
echo "[$(date '+%H:%M:%S')] 删除 2026-04-17 ~ 2026-04-18 (~89万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-17' AND timestamp < '2026-04-18';"
wait

# 4月18日~4月19日（231万）
echo "[$(date '+%H:%M:%S')] 删除 2026-04-18 ~ 2026-04-19 上午 (~115万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-18' AND timestamp < '2026-04-18 12:00';"
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-04-18 下午 ~ 2026-04-19 上午 (~115万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-18 12:00' AND timestamp < '2026-04-19 12:00';"
wait
echo "[$(date '+%H:%M:%S')] 删除 2026-04-19 下午 (~115万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-19 12:00' AND timestamp < '2026-04-20';"
wait

# 4月20日~4月21日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-20 ~ 2026-04-21 (~28万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-20' AND timestamp < '2026-04-21';"
wait

# 4月21日~4月23日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-21 ~ 2026-04-23 (~15万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-21' AND timestamp < '2026-04-23';"
wait

# 4月23日~4月24日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-23 ~ 2026-04-24 (~82万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-23' AND timestamp < '2026-04-24';"
wait

# 4月24日~4月25日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-24 ~ 2026-04-25 (~97万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-24' AND timestamp < '2026-04-25';"
wait

# 4月25日~4月26日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-25 ~ 2026-04-26 (~66万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-25' AND timestamp < '2026-04-26';"
wait

# 4月26日~4月28日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-26 ~ 2026-04-28 (~96万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-26' AND timestamp < '2026-04-28';"
wait

# 4月28日~4月29日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-28 ~ 2026-04-29 (~75万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-28' AND timestamp < '2026-04-29';"
wait

# 4月29日~4月30日
echo "[$(date '+%H:%M:%S')] 删除 2026-04-29 ~ 2026-04-30 (~150万) ..."
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0; DELETE FROM time_series_data WHERE timestamp >= '2026-04-29' AND timestamp < '2026-04-30';"
wait

echo ""
echo "=== time_series_data 删除完成，开始 VACUUM FULL ==="
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "VACUUM FULL time_series_data;"

echo ""
echo "=== time_series_data 当前数据量 ==="
docker exec ${CONTAINER} psql -U ${USER} -d ${DB} -c "
SELECT COUNT(*) as remaining_rows, MIN(timestamp) as min_time, MAX(timestamp) as max_time FROM time_series_data;
"

echo ""
echo "=== 所有清理完成 ==="
