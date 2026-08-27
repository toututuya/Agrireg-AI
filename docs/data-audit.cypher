// Entity inventory
MATCH (node)
UNWIND labels(node) AS label
RETURN label, count(node) AS nodes
ORDER BY nodes DESC;

// Relationship inventory
MATCH ()-[relation]->()
RETURN type(relation) AS relationType, count(relation) AS relationships
ORDER BY relationships DESC;

// Registration dataset signatures
MATCH (registration:RegisterNumber)
RETURN
  count(registration) AS registrations,
  sum(CASE WHEN registration.`Member State of origin` = 'China' THEN 1 ELSE 0 END) AS china,
  sum(CASE WHEN registration.Status IS NOT NULL THEN 1 ELSE 0 END) AS germany,
  sum(CASE WHEN registration.`Approval number/Member State of origin` IS NOT NULL THEN 1 ELSE 0 END) AS euMutualRecognition,
  sum(CASE WHEN registration.`Member State of origin` IS NULL
            AND registration.Status IS NULL THEN 1 ELSE 0 END) AS unclassified;

// Countries and regions represented by the source field
MATCH (registration:RegisterNumber)
WITH trim(toString(registration.`Member State of origin`)) AS jurisdiction
WHERE jurisdiction <> '' AND jurisdiction <> '-'
RETURN jurisdiction, count(*) AS records
ORDER BY records DESC;

// Records that need provenance backfilling
MATCH (registration:RegisterNumber)
WHERE registration.source_url IS NULL
   OR registration.collected_at IS NULL
RETURN registration.name AS registrationNumber
LIMIT 100;
