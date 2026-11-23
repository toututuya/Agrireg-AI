// Apply after restoring a cleaned graph. Match existing canonical nodes only.
UNWIND [
  {entity: 'Crop:apple', aliases: ['苹果']},
  {entity: 'Crop:apple tree', aliases: ['苹果树']},
  {
    entity: 'Disease:leaf rust',
    aliases: ['叶锈病', '叶锈'],
    definition: '叶锈病是在叶片上发生的一类真菌性锈病。以小麦叶锈病为例，病原是小麦叶锈菌（Puccinia triticina），病叶上表面常见圆形褐色孢子堆。具体病原随寄主作物而异。',
    sourceTitle: '美国农业部农业研究局 · Wheat leaf rust',
    sourceUrl: 'https://www.ars.usda.gov/midwest-area/stpaul/cereal-disease-lab/docs/cereal-rusts/wheat-leaf-rust/'
  }
] AS row
MATCH (node {canonical_id: row.entity})
SET node.aliases = reduce(aliases = coalesce(node.aliases, []), alias IN row.aliases |
  CASE WHEN alias IN aliases THEN aliases ELSE aliases + [alias] END)
FOREACH (_ IN CASE WHEN row.definition IS NOT NULL AND node.definition_zh IS NULL THEN [1] ELSE [] END |
  SET node.definition_zh = row.definition,
      node.definition_source_title = row.sourceTitle,
      node.definition_source_url = row.sourceUrl
)
RETURN node.canonical_id AS entity, node.aliases AS aliases;
