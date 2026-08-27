// AgriReg AI graph cleaning pipeline, version 2026-08-27-v1.
// Run this only against a database restored from the immutable source dump.

// 1. Normalize entity names while retaining the imported value for audit.
MATCH (n)
WHERE n.name IS NOT NULL
WITH n, trim(apoc.text.replace(toString(n.name), '\\s+', ' ')) AS cleanedName
SET n.raw_name = coalesce(n.raw_name, toString(n.name)),
    n.name = cleanedName,
    n.normalized_name = toLower(cleanedName),
    n.cleaning_version = '2026-08-27-v1';

// 2. Remove empty and placeholder-valued fields. The immutable dump is the raw-data record.
MATCH (n)
WITH n, [key IN keys(n)
         WHERE NOT key IN ['name', 'raw_name', 'normalized_name', 'cleaning_version']
           AND CASE
             WHEN apoc.meta.type(n[key]) = 'STRING'
               THEN trim(toLower(n[key])) IN ['', '-', '--', 'n/a', 'na', 'null', 'none', '*']
             ELSE false
           END]
         AS placeholderKeys
WHERE size(placeholderKeys) > 0
SET n.removed_placeholder_count = size(placeholderKeys)
WITH n, placeholderKeys
CALL apoc.create.removeProperties(n, placeholderKeys) YIELD node
RETURN count(node) AS nodesWithPlaceholdersRemoved;

// 3. Hide a systematically mistranslated field when its value conflicts with the entity name.
MATCH (n:ActiveSubstance)
WHERE n.`Chinese common name` IS NOT NULL
  AND toLower(trim(apoc.text.replace(toString(n.`Chinese common name`), '\\s+', ' '))) <> n.normalized_name
SET n.quality_issues = coalesce(n.quality_issues, []) + ['unverified_chinese_common_name_removed']
REMOVE n.`Chinese common name`;

// 4. Remove known mojibake Russian-name fields from the serving copy.
MATCH (n:ActiveSubstance)
WITH n, [key IN keys(n) WHERE key STARTS WITH 'Russian name'] AS mojibakeKeys
WHERE size(mojibakeKeys) > 0
SET n.quality_issues = apoc.coll.toSet(coalesce(n.quality_issues, []) + ['mojibake_russian_name_removed'])
WITH n, mojibakeKeys
CALL apoc.create.removeProperties(n, mojibakeKeys) YIELD node
RETURN count(node) AS nodesWithMojibakeRemoved;

// 5. Quarantine known Chlorantraniliprole fields that contain Chlorpyrifos data.
MATCH (n:ActiveSubstance)
WHERE n.normalized_name = 'chlorantraniliprole'
SET n.data_quality_status = 'quarantined',
    n.quality_issues = apoc.coll.toSet(coalesce(n.quality_issues, []) + [
      'cross_entity_translation_removed',
      'unverified_mode_of_action_removed',
      'unverified_mrl_description_removed'
    ])
REMOVE n.`Chinese common name`,
       n.`Mode of action`,
       n.`Maximum Residue Limits (MRLs) and Related Regulations (with attention to timeliness) MRLs and Texts`;

// 6. Merge case and whitespace duplicates for controlled entity types.
// The highest-degree, richest node is kept; aliases and legacy internal IDs retain traceability.
UNWIND ['Crop', 'Disease', 'ActiveSubstance', 'PesticideCategory'] AS targetLabel
MATCH (n)
WHERE targetLabel IN labels(n)
  AND n.normalized_name IS NOT NULL
  AND NOT n.normalized_name IN ['', '-', '--', 'n/a', 'unknown']
WITH targetLabel, n.normalized_name AS normalizedName, collect(n) AS candidates
WHERE size(candidates) > 1
WITH targetLabel, normalizedName, candidates,
     apoc.coll.toSet([
       candidate IN candidates
       WHERE candidate.`CAS registry number` IS NOT NULL
       | trim(toString(candidate.`CAS registry number`))
     ]) AS casValues
WHERE targetLabel <> 'ActiveSubstance' OR size(casValues) <= 1
UNWIND candidates AS candidate
WITH targetLabel, normalizedName, candidate,
     size((candidate)--()) AS degree,
     size(keys(candidate)) AS propertyCount
ORDER BY targetLabel, normalizedName, degree DESC, propertyCount DESC, id(candidate)
WITH targetLabel, normalizedName, collect(candidate) AS orderedNodes
WITH orderedNodes,
     apoc.coll.toSet([candidate IN orderedNodes | candidate.raw_name]) AS aliases,
     [candidate IN orderedNodes | id(candidate)] AS legacyIds
WITH orderedNodes, aliases, legacyIds,
     [alias IN aliases WHERE alias =~ '^[A-Z0-9].*'] AS displayCandidates
WITH orderedNodes, aliases, legacyIds, displayCandidates, orderedNodes[0] AS canonicalNode
SET canonicalNode.aliases = aliases,
    canonicalNode.merged_legacy_ids = legacyIds,
    canonicalNode.name = coalesce(head(displayCandidates), canonicalNode.name)
WITH orderedNodes
CALL apoc.refactor.mergeNodes(
  orderedNodes,
  {properties: 'discard', mergeRels: true, produceSelfRel: false}
) YIELD node
SET node.normalized_name = toLower(trim(apoc.text.replace(node.name, '\\s+', ' '))),
    node.cleaning_version = '2026-08-27-v1'
RETURN count(node) AS duplicateGroupsMerged;

// 7. Collapse relationships that became identical after node merging.
MATCH (source)-[relationship]->(target)
WITH source, target, type(relationship) AS relationshipType, collect(relationship) AS relationships
WHERE size(relationships) > 1
FOREACH (duplicate IN tail(relationships) | DELETE duplicate)
RETURN sum(size(relationships) - 1) AS duplicateRelationshipsRemoved;

// 8. Add a canonical ISO date without discarding source-specific date fields.
MATCH (registration:RegisterNumber)
WITH registration,
     CASE
       WHEN registration.`Time expiry date_y` IS NOT NULL
         THEN trim(toString(registration.`Time expiry date_y`))
       WHEN registration.`valid until` IS NOT NULL
         THEN trim(toString(registration.`valid until`))
       WHEN registration.`End of approval` IS NOT NULL
         THEN trim(toString(registration.`End of approval`))
       ELSE NULL
     END AS rawDate
WITH registration, rawDate,
     split(split(coalesce(rawDate, ''), ' ')[0], '-') AS hyphenParts,
     split(coalesce(rawDate, ''), '.') AS dotParts
SET registration.valid_until_raw = rawDate,
    registration.valid_until = CASE
      WHEN rawDate =~ '\\d{4}-\\d{1,2}-\\d{1,2}.*'
        THEN hyphenParts[0] + '-' + right('0' + hyphenParts[1], 2) + '-' + right('0' + hyphenParts[2], 2)
      WHEN rawDate =~ '\\d{2}\\.\\d{2}\\.\\d{2}'
        THEN '20' + dotParts[2] + '-' + dotParts[1] + '-' + dotParts[0]
      ELSE NULL
    END,
    registration.valid_until_parse_status = CASE
      WHEN rawDate IS NULL THEN 'missing'
      WHEN rawDate =~ '\\d{4}-\\d{1,2}-\\d{1,2}.*' OR rawDate =~ '\\d{2}\\.\\d{2}\\.\\d{2}' THEN 'parsed'
      ELSE 'unparsed'
    END;

// 9. Add a common jurisdiction field and record whether it was inferred.
MATCH (registration:RegisterNumber)
WITH registration,
     trim(toString(registration.`Member State of origin`)) AS importedJurisdiction
SET registration.jurisdiction = CASE
      WHEN importedJurisdiction IS NOT NULL AND importedJurisdiction <> '' THEN importedJurisdiction
      WHEN registration.`Effect Type` IS NOT NULL OR registration.`Time expiry date_y` IS NOT NULL THEN 'China'
      WHEN registration.Status IS NOT NULL THEN 'Germany'
      ELSE 'Unclassified'
    END,
    registration.jurisdiction_inferred = importedJurisdiction IS NULL OR importedJurisdiction = '',
    registration.provenance_status = CASE
      WHEN registration.source_url IS NULL THEN 'missing_source_url'
      ELSE 'source_linked'
    END;

// 10. Add stable application-facing IDs. Registration numbers are scoped by jurisdiction.
MATCH (n)
WITH n, head(labels(n)) AS entityType
SET n.canonical_id = entityType + ':' + CASE
  WHEN entityType = 'RegisterNumber'
    THEN toLower(coalesce(n.jurisdiction, 'unclassified')) + ':' + coalesce(n.normalized_name, toLower(trim(toString(n.name))))
  WHEN entityType = 'ActiveSubstance' AND n.`CAS registry number` IS NOT NULL
    THEN trim(toString(n.`CAS registry number`))
  ELSE coalesce(n.normalized_name, toLower(trim(toString(n.name))))
END;

// 11. Remove placeholder entities and their non-semantic edges from the serving copy.
MATCH (n)
WHERE n.name IS NULL OR trim(toString(n.name)) IN ['', '-', '--', 'n/a', 'unknown']
DETACH DELETE n;

// Keep remaining incomplete records for audit, but mark them so the serving layer can exclude them.
MATCH (n)
WHERE NOT (n)--()
SET n.data_quality_status = CASE
      WHEN n.data_quality_status = 'quarantined' THEN n.data_quality_status
      ELSE 'orphan'
    END,
    n.quality_issues = apoc.coll.toSet(coalesce(n.quality_issues, []) + ['no_relationships']);

MATCH (n)
WHERE n.name IS NOT NULL AND size(n.name) > 120
SET n.quality_issues = apoc.coll.toSet(coalesce(n.quality_issues, []) + ['long_name_review_required']);

// 12. Index the canonical lookup fields used by application queries.
CREATE INDEX crop_normalized_name IF NOT EXISTS FOR (n:Crop) ON (n.normalized_name);
CREATE INDEX disease_normalized_name IF NOT EXISTS FOR (n:Disease) ON (n.normalized_name);
CREATE INDEX active_substance_normalized_name IF NOT EXISTS FOR (n:ActiveSubstance) ON (n.normalized_name);
CREATE INDEX active_substance_cas IF NOT EXISTS FOR (n:ActiveSubstance) ON (n.`CAS registry number`);
CREATE INDEX pesticide_category_normalized_name IF NOT EXISTS FOR (n:PesticideCategory) ON (n.normalized_name);
CREATE INDEX registration_normalized_name IF NOT EXISTS FOR (n:RegisterNumber) ON (n.normalized_name);
CREATE INDEX registration_canonical_id IF NOT EXISTS FOR (n:RegisterNumber) ON (n.canonical_id);
CREATE INDEX chemical_classes_normalized_name IF NOT EXISTS FOR (n:ChemicalClasses) ON (n.normalized_name);
CREATE INDEX target_site_normalized_name IF NOT EXISTS FOR (n:TargetSite) ON (n.normalized_name);
CREATE INDEX mode_of_action_normalized_name IF NOT EXISTS FOR (n:ModeOfAction) ON (n.normalized_name);
