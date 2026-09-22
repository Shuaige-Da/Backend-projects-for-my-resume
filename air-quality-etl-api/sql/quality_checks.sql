-- Import counters must reconcile.
SELECT id_import_file, filename, total_rows, accepted_rows, rejected_rows
FROM air_quality.import_file
WHERE total_rows <> accepted_rows + rejected_rows;

-- No orphan measurements.
SELECT COUNT(*) AS orphan_measurements
FROM air_quality.measurement AS measurement
LEFT JOIN air_quality.station AS station
  ON station.id_station = measurement.id_station
WHERE station.id_station IS NULL;

-- The natural measurement key must remain unique.
SELECT id_station, observed_at, COUNT(*) AS duplicate_count
FROM air_quality.measurement
GROUP BY id_station, observed_at
HAVING COUNT(*) > 1;

-- Database constraints should make this empty; retained as an operational check.
SELECT id_measurement, aqi
FROM air_quality.measurement
WHERE aqi < 0 OR aqi > 500;

-- Missing-value rates by year, useful for detecting source schema changes.
SELECT
    EXTRACT(YEAR FROM observed_at)::INTEGER AS year,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE aqi IS NULL) AS missing_aqi,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE aqi IS NULL) / NULLIF(COUNT(*), 0),
        2
    ) AS missing_aqi_percent,
    COUNT(*) FILTER (WHERE quality_flags IS NOT NULL) AS rows_with_quality_flags
FROM air_quality.measurement
GROUP BY year
ORDER BY year;
