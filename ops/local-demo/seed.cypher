// Synthetic fixture for a separate local Neo4j database.
MERGE (ingredient:ActiveSubstance {name: 'AgriReg Demo A'})
SET ingredient.normalized_name = 'agrireg demo a',
    ingredient.aliases = ['\u5355\u4e00\u6d4b\u8bd5\u522b\u540d', '\u5171\u4eab\u6837\u4f8b\u522b\u540d'],
    ingredient.source_name = 'AgriReg synthetic demo';

MERGE (alternative:ActiveSubstance {name: 'AgriReg Demo B'})
SET alternative.normalized_name = 'agrireg demo b',
    alternative.aliases = ['\u5171\u4eab\u6837\u4f8b\u522b\u540d'],
    alternative.source_name = 'AgriReg synthetic demo';

MERGE (record:RegisterNumber {name: 'AGRIREG-DEMO-001'})
SET record.normalized_name = 'agrireg-demo-001',
    record.canonical_id = 'agrireg:demo:001',
    record.source_name = 'AgriReg synthetic demo',
    record.registration_status = 'synthetic example';

MERGE (crop:Crop {name: 'AgriReg Demo Crop'})
SET crop.normalized_name = 'agrireg demo crop',
    crop.source_name = 'AgriReg synthetic demo';

MERGE (disease:Disease {name: 'AgriReg Demo Disease'})
SET disease.normalized_name = 'agrireg demo disease',
    disease.source_name = 'AgriReg synthetic demo';

MATCH (ingredient:ActiveSubstance {name: 'AgriReg Demo A'}),
      (record:RegisterNumber {name: 'AGRIREG-DEMO-001'}),
      (crop:Crop {name: 'AgriReg Demo Crop'}),
      (disease:Disease {name: 'AgriReg Demo Disease'})
MERGE (ingredient)-[:RELATED_TO]->(record)
MERGE (record)-[:RELATED_TO]->(crop)
MERGE (record)-[:RELATED_TO]->(disease);
