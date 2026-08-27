// Post-cleaning acceptance checks.

MATCH (n)
RETURN count(n) AS nodes;

MATCH ()-[r]->()
RETURN count(r) AS relationships;

MATCH (n)
UNWIND labels(n) AS label
RETURN label, count(*) AS nodes
ORDER BY nodes DESC;

UNWIND ['Crop', 'Disease', 'ActiveSubstance', 'PesticideCategory'] AS targetLabel
MATCH (n)
WHERE targetLabel IN labels(n) AND n.normalized_name IS NOT NULL
WITH targetLabel, n.normalized_name AS normalizedName, count(*) AS copies
WHERE copies > 1
RETURN targetLabel, count(*) AS duplicateGroups, sum(copies - 1) AS excessNodes
ORDER BY targetLabel;

MATCH (source)-[relationship]->(target)
WITH source, target, type(relationship) AS relationshipType, count(*) AS copies
WHERE copies > 1
RETURN count(*) AS duplicateRelationshipGroups, sum(copies - 1) AS excessRelationships;

MATCH (n)
RETURN
  sum(CASE WHEN n.name IS NULL OR trim(toString(n.name)) IN ['', '-', '--', 'n/a', 'unknown'] THEN 1 ELSE 0 END) AS invalidNames,
  sum(CASE WHEN n.raw_name IS NOT NULL AND n.name <> n.raw_name THEN 1 ELSE 0 END) AS normalizedNames,
  sum(CASE WHEN n.data_quality_status = 'orphan' THEN 1 ELSE 0 END) AS orphanNodes,
  sum(CASE WHEN n.data_quality_status = 'quarantined' THEN 1 ELSE 0 END) AS quarantinedNodes;

MATCH (n)
UNWIND keys(n) AS key
WITH n, key
WHERE NOT key IN ['name', 'raw_name', 'normalized_name']
  AND CASE
    WHEN apoc.meta.type(n[key]) = 'STRING'
      THEN trim(toLower(n[key])) IN ['', '-', '--', 'n/a', 'na', 'null', 'none', '*']
    ELSE false
  END
RETURN count(*) AS remainingPlaceholderValues;

MATCH (n:ActiveSubstance)
UNWIND keys(n) AS key
WITH key
WHERE key STARTS WITH 'Russian name'
RETURN count(*) AS remainingMojibakeFields;

MATCH (registration:RegisterNumber)
RETURN
  count(*) AS registrations,
  sum(CASE WHEN registration.valid_until_parse_status = 'parsed' THEN 1 ELSE 0 END) AS parsedValidUntil,
  sum(CASE WHEN registration.valid_until_parse_status = 'unparsed' THEN 1 ELSE 0 END) AS unparsedValidUntil,
  sum(CASE WHEN registration.valid_until_parse_status = 'missing' THEN 1 ELSE 0 END) AS missingValidUntil,
  sum(CASE WHEN registration.provenance_status = 'missing_source_url' THEN 1 ELSE 0 END) AS missingSourceUrl;

MATCH (n:ActiveSubstance)
WHERE n.normalized_name = 'chlorantraniliprole'
RETURN n.name AS name,
       n.data_quality_status AS dataQualityStatus,
       n.quality_issues AS qualityIssues,
       n.`Chinese common name` AS removedChineseCommonName,
       n.`Mode of action` AS removedModeOfAction;

// Review suspicious machine-translated or field-concatenated names instead of deleting them automatically.
MATCH (n)
WHERE toLower(toString(n.name)) CONTAINS 'hygiene'
   OR toString(n.name) =~ '(?i).*(\\b[A-Za-z]+\\b)(?:\\s+\\1){2,}.*'
RETURN id(n) AS nodeId, labels(n)[0] AS label, n.name AS suspiciousName
ORDER BY label, suspiciousName;

SHOW INDEXES
YIELD name, state, labelsOrTypes, properties
WHERE name IN [
  'crop_normalized_name',
  'disease_normalized_name',
  'active_substance_normalized_name',
  'active_substance_cas',
  'pesticide_category_normalized_name',
  'registration_normalized_name',
  'chemical_classes_normalized_name',
  'target_site_normalized_name',
  'mode_of_action_normalized_name',
  'registration_canonical_id'
]
RETURN name, state, labelsOrTypes, properties
ORDER BY name;
