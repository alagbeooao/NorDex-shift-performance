USE NorDexManufacturing;
GO

SELECT * FROM Shift_Master;
SELECT TOP 10 * FROM Production_Log;
SELECT TOP 20 * FROM Operator_Assignment;

---- query 1: Reveals productivity imbalance between morning, evening, and night shifts.
SELECT 
    sm.shift_name,
    AVG(pl.units_produced)           AS avg_units,
    AVG(pl.shift_efficiency_score)   AS avg_efficiency_score
FROM Production_Log pl
JOIN Shift_Master sm ON pl.shift_id = sm.shift_id
GROUP BY sm.shift_name
ORDER BY avg_units DESC;



---- query 2: Highlights which shifts suffer most from equipment downtime.
SELECT 
    sm.shift_name,
    SUM(ml.downtime_minutes) AS total_downtime
FROM Machine_Log ml
JOIN Shift_Master sm ON ml.shift_id = sm.shift_id
GROUP BY sm.shift_name
ORDER BY total_downtime desc;


---- query 3: Tests whether operator experience correlates with product quality.
SELECT 
    oa.experience_level,
    AVG(pl.defect_count)            AS avg_defects,
    AVG(pl.shift_efficiency_score)  AS avg_efficiency_score
FROM Production_Log pl
JOIN Operator_Assignment oa 
    ON pl.operator_id = oa.operator_id
   AND pl.shift_id     = oa.shift_id
   AND pl.date         = oa.date
GROUP BY oa.experience_level
ORDER BY oa.experience_level;


---- query 4: Identifies machines that require frequent maintenance and contribute to downtime clustering.
SELECT Top 10
    machine_id,
    COUNT(*) AS maintenance_events,
    SUM(downtime_minutes) AS total_downtime
FROM Maintenance_Records
GROUP BY machine_id
ORDER BY maintenance_events DESC;


---- query 5: Shows the most common defect types impacting production quality.
SELECT 
    defect_type,
    COUNT(*) AS defect_count
FROM Quality_Control
GROUP BY defect_type
ORDER BY defect_count DESC;


---- query 6: Explores whether temperature or humidity variations influence production efficiency. PUT ICE ON THIS FOR NOW!!!
SELECT 
    ed.temperature,
    ed.humidity,
    AVG(pl.units_produced) AS avg_units
FROM Environmental_Data AS ed
JOIN Production_Log AS pl 
    ON  ed.shift_id = pl.shift_id
    AND CONVERT(date, ed.[timestamp]) = CONVERT(date, pl.[date])
GROUP BY 
    ed.temperature, 
    ed.humidity
ORDER BY 
    avg_units DESC;


-- shift level combined metrics
SELECT 
    s.shift_name,
    AVG(p.units_produced)           AS avg_units,
    AVG(p.defect_count)             AS avg_defects,
    AVG(m.downtime_minutes)         AS avg_downtime,
    AVG(p.shift_efficiency_score)   AS avg_efficiency_score
FROM Production_Log p
JOIN Shift_Master s ON p.shift_id = s.shift_id
JOIN Machine_Log m 
    ON p.machine_id = m.machine_id 
   AND p.shift_id   = m.shift_id 
   AND p.date       = m.date
GROUP BY s.shift_name
ORDER BY avg_units DESC;


--- OEE Degradation
/* ============================================================
   STEP 1: Clean Production Table  
   One row per production event (remove duplicates)
   ============================================================ */
WITH prod AS (
    SELECT DISTINCT
        production_id,
        shift_id,
        date,
        units_produced,
        defect_count
    FROM Production_Log
),

/* ============================================================
   STEP 2: Clean Machine Table  
   One row per machine per shift (remove duplicates)
   ============================================================ */
mach AS (
    SELECT DISTINCT
        machine_id,
        shift_id,
        date,
        downtime_minutes
    FROM Machine_Log
),

/* ============================================================
   STEP 3: Machine-Level Availability  
   Formula: 1 − (downtime_minutes / planned_minutes)
   Planned shift = 7.5 hours = 450 minutes
   ============================================================ */
avail_machine AS (
    SELECT
        machine_id,
        shift_id,
        date,
        1 - (downtime_minutes / (7.5 * 60.0)) AS avail_machine
    FROM mach
),

/* ============================================================
   STEP 4: Shift-Level Availability  
   Average the availability of all machines in that shift
   Clip values between 0 and 1 (same as Python)
   ============================================================ */
avail_agg AS (
    SELECT
        date,
        shift_id,
        AVG(
            CASE 
                WHEN avail_machine < 0 THEN 0
                WHEN avail_machine > 1 THEN 1
                ELSE avail_machine 
            END
        ) AS availability
    FROM avail_machine
    GROUP BY date, shift_id
),

/* ============================================================
   STEP 5: Merge Availability into Production  
   If no availability data exists → assume availability = 1
   (matches Python: merged['availability'].fillna(1))
   ============================================================ */
merged AS (
    SELECT
        p.date,
        p.units_produced,
        p.defect_count,
        COALESCE(a.availability, 1.0) AS availability
    FROM prod p
    LEFT JOIN avail_agg a
        ON p.date = a.date 
        AND p.shift_id = a.shift_id
),

/* ============================================================
   STEP 6: Row-Level OEE Calculation  
   OEE = Availability × Performance × Quality

   Performance = units / (theoretical_rate × planned_hours)
               = units / (100 × 7.5)

   Quality = (good units / total units)
           = 1 − (defects / units)
   ============================================================ */
oee_row AS (
    SELECT
        date,
        availability *
        (units_produced / (100.0 * 7.5)) *
        (1 - defect_count * 1.0 / units_produced) AS oee
    FROM merged
    WHERE units_produced > 0
)

/* ============================================================
   STEP 7: Final Monthly OEE  
   Average row-level OEE (same as Python)
   ============================================================ */
SELECT
    DATEPART(MONTH, date) AS month,
    COUNT(*) AS total_records,
    AVG(oee) AS oee
FROM oee_row
GROUP BY DATEPART(MONTH, date)
ORDER BY month;



-- Create a view for consolidated dataset
CREATE VIEW v1_ShiftPerformance AS
SELECT 
    -- Shift details
    sm.shift_id,
    sm.shift_name,
    sm.start_time,
    sm.end_time,
    sm.supervisor_id,

    -- Production details
    pl.production_id,
    pl.date,
    pl.units_produced,
    pl.defect_count,
    pl.cycle_time_avg,
	pl.shift_efficiency_score,

    -- Operator details
    oa.operator_id,
    oa.name AS operator_name,
    oa.experience_level,
    oa.skill_category,

    -- Machine details
    ml.machine_id,
    ml.runtime_hours,
    ml.downtime_minutes,
    ml.maintenance_flag,
    ml.machine_status,

    -- Maintenance details
    mr.maintenance_id,
    mr.issue_type,
    mr.downtime_minutes AS maintenance_downtime,
    mr.resolved_by,

    -- Quality control details
    qc.qc_id,
    qc.defect_type,
    qc.severity,
    qc.inspection_result,

    -- Environmental details
    ed.temperature,
    ed.humidity,
    ed.timestamp

FROM Production_Log pl
JOIN Shift_Master sm 
    ON pl.shift_id = sm.shift_id
JOIN Operator_Assignment oa 
    ON pl.operator_id = oa.operator_id 
   AND pl.shift_id = oa.shift_id 
   AND pl.date = oa.date
JOIN Machine_Log ml 
    ON pl.machine_id = ml.machine_id 
   AND pl.shift_id = ml.shift_id 
   AND pl.date = ml.date
LEFT JOIN Maintenance_Records mr 
    ON ml.machine_id = mr.machine_id 
   AND pl.date = mr.date
LEFT JOIN Quality_Control qc 
    ON pl.production_id = qc.production_id
LEFT JOIN Environmental_Data ed 
    ON pl.shift_id = ed.shift_id 
   AND CAST(ed.timestamp AS DATE) = pl.date;

select top 5 * from v1_ShiftPerformance;

SELECT 
    sp.shift_name,

    -- Production KPIs
    AVG(sp.units_produced) AS avg_units_produced,
    SUM(sp.units_produced) AS total_units_produced,
    AVG(sp.cycle_time_avg) AS avg_cycle_time,

    -- Output per hour (units per machine-hour across shift)
    CASE 
        WHEN SUM(sp.runtime_hours) = 0 THEN NULL
        ELSE SUM(sp.units_produced) / SUM(sp.runtime_hours)
    END AS output_per_hour,

    -- Quality KPIs
    AVG(sp.defect_count) AS avg_defect_count,
    CASE 
        WHEN SUM(sp.units_produced) = 0 THEN NULL
        ELSE SUM(sp.defect_count) * 1.0 / SUM(sp.units_produced)
    END AS defect_rate,

    -- Downtime KPIs
    AVG(sp.downtime_minutes) AS avg_downtime_minutes,
    SUM(sp.downtime_minutes) AS total_downtime_minutes,

    -- Machine Availability KPI
    CASE 
        WHEN SUM(sp.runtime_hours) + (SUM(sp.downtime_minutes) / 60.0) = 0 THEN NULL
        ELSE SUM(sp.runtime_hours) / 
            (SUM(sp.runtime_hours) + (SUM(sp.downtime_minutes) / 60.0))
    END AS availability,

    -- Efficiency Score
    AVG(sp.shift_efficiency_score) AS avg_shift_efficiency_score,

    -- OEE KPI (Availability × Performance × Quality)
    CASE 
        WHEN SUM(sp.units_produced) = 0 THEN NULL
        ELSE 
            -- Availability
            ( SUM(sp.runtime_hours) / 
              (SUM(sp.runtime_hours) + (SUM(sp.downtime_minutes) / 60.0)) )
            *
            -- Performance: units / (100 units/hr × 7.5 hours)
            ( SUM(sp.units_produced) / (100.0 * 7.5) )
            *
            -- Quality
            (1 - (SUM(sp.defect_count) * 1.0 / SUM(sp.units_produced)))
    END AS oee

FROM v_ShiftPerformance sp
GROUP BY 
    sp.shift_name
ORDER BY 
    avg_units_produced DESC;

