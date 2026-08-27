package com.sc.pesticideknowledgemappingsystem.service;

import org.neo4j.ogm.session.Session;
import org.neo4j.ogm.session.SessionFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class GraphExploreService {

    private static final int MAX_NEIGHBORS = 48;
    private static final int MAX_CENTER_PROPERTIES = 28;
    private static final int MAX_NEIGHBOR_PROPERTIES = 8;
    private static final int MAX_PROPERTY_LENGTH = 600;
    private static final List<String> IMPORTANT_PROPERTIES = Arrays.asList(
            "name", "Trade name", "Pesticide name", "Active Ingredient",
            "jurisdiction", "valid_until",
            "Member State of origin", "Status", "Registration Status",
            "End of approval", "Time expiry date_y", "valid until",
            "Start of admission", "Date of approval:", "Date of reauthorization:",
            "source", "Source", "source_url", "original_url", "collected_at", "updated_at",
            "2D Chemical structure", "Image", "image", "image_url", "Photo", "photo",
            "Field of application", "Area of application", "Pesticide category",
            "Symptoms of infestation", "pathogen", "geographic distribution",
            "Method of application", "Introduction", "Mode of action", "Resistance",
            "CAS registry number", "Molecular or Experimental Formulas Formul", "MF/MW"
    );
    private static final Set<String> INTERNAL_PROPERTIES = new LinkedHashSet<>(Arrays.asList(
            "raw_name", "normalized_name", "canonical_id", "aliases", "merged_legacy_ids",
            "cleaning_version", "removed_placeholder_count", "data_quality_status", "quality_issues",
            "valid_until_raw", "valid_until_parse_status", "jurisdiction_inferred", "provenance_status"
    ));

    @Autowired
    private SessionFactory sessionFactory;

    public Map<String, Object> search(String keyword) {
        Session session = sessionFactory.openSession();
        Long nodeId = resolveNodeId(session, keyword);
        Map<String, Object> parameters = new LinkedHashMap<>();
        parameters.put("nodeId", nodeId == null ? -1L : nodeId);
        return executeGraphQuery(session, graphByIdCypher(), parameters, keyword);
    }

    public Map<String, Object> explore(long nodeId) {
        Session session = sessionFactory.openSession();
        Map<String, Object> parameters = new LinkedHashMap<>();
        parameters.put("nodeId", nodeId);
        return executeGraphQuery(session, graphByIdCypher(), parameters, null);
    }

    public Map<String, Object> findPath(String sourceKeyword, String targetKeyword) {
        Session session = sessionFactory.openSession();
        Long sourceId = resolveNodeId(session, sourceKeyword);
        Long targetId = resolveNodeId(session, targetKeyword);
        String cypher =
                "MATCH (source), (target) " +
                "WHERE id(source) = $sourceId AND id(target) = $targetId " +
                "MATCH path = shortestPath((source)-[*..6]-(target)) " +
                "UNWIND relationships(path) AS relation " +
                "WITH source, target, relation, startNode(relation) AS leftNode, endNode(relation) AS rightNode " +
                "RETURN id(source) AS centerId, id(target) AS targetId, " +
                "id(leftNode) AS leftId, labels(leftNode)[0] AS leftLabel, " +
                "properties(leftNode) AS leftProperties, id(rightNode) AS rightId, " +
                "labels(rightNode)[0] AS rightLabel, properties(rightNode) AS rightProperties, " +
                "type(relation) AS relationType";

        Map<String, Object> parameters = new LinkedHashMap<>();
        parameters.put("sourceId", sourceId == null ? -1L : sourceId);
        parameters.put("targetId", targetId == null ? -1L : targetId);
        return executePathQuery(session, cypher, parameters, sourceKeyword, targetKeyword);
    }

    private String graphByIdCypher() {
        return "MATCH (center) WHERE id(center) = $nodeId " +
                "OPTIONAL MATCH (center)-[relation]-(neighbor) " +
                "WITH center, relation, neighbor LIMIT " + MAX_NEIGHBORS + " " +
                "RETURN id(center) AS centerId, labels(center)[0] AS centerLabel, " +
                "properties(center) AS centerProperties, id(neighbor) AS neighborId, " +
                "labels(neighbor)[0] AS neighborLabel, properties(neighbor) AS neighborProperties, " +
                "type(relation) AS relationType, id(startNode(relation)) AS relationSourceId, " +
                "id(endNode(relation)) AS relationTargetId";
    }

    private Long resolveNodeId(Session session, String keyword) {
        String exactCypher =
                "CALL { " +
                "MATCH (node:ActiveSubstance) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:Crop) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:Disease) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:RegisterNumber) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:ChemicalClasses) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:PesticideCategory) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:TargetSite) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:ModeOfAction) WHERE node.normalized_name = $normalized " +
                "RETURN id(node) AS nodeId, 0 AS matchRank " +
                "UNION ALL MATCH (node:ActiveSubstance) " +
                "WHERE node.`CAS registry number` = $keyword " +
                "RETURN id(node) AS nodeId, 1 AS matchRank " +
                "} RETURN nodeId ORDER BY matchRank, nodeId LIMIT 1";

        Map<String, Object> parameters = new LinkedHashMap<>();
        parameters.put("normalized", normalizeKeyword(keyword));
        parameters.put("keyword", keyword.trim());
        Long exact = firstNodeId(session.query(exactCypher, parameters));
        if (exact != null) return exact;

        String fallbackCypher =
                "MATCH (node) " +
                "WHERE " + searchableText("node") + " CONTAINS toLower($keyword) " +
                "WITH node, " + matchRank("node", "keyword") + " AS matchRank " +
                "ORDER BY matchRank, size(" + primaryName("node") + "), id(node) LIMIT 1 " +
                "RETURN id(node) AS nodeId";
        return firstNodeId(session.query(fallbackCypher, parameters));
    }

    private Long firstNodeId(Iterable<Map<String, Object>> rows) {
        for (Map<String, Object> row : rows) return asLong(row.get("nodeId"));
        return null;
    }

    private String normalizeKeyword(String keyword) {
        return keyword.trim().replaceAll("\\s+", " ").toLowerCase(Locale.ROOT);
    }

    public Map<String, Object> stats() {
        String cypher =
                "MATCH (node) WITH count(node) AS nodeCount " +
                "MATCH ()-[relation]->() RETURN nodeCount, count(relation) AS relationshipCount";
        Session session = sessionFactory.openSession();
        Iterable<Map<String, Object>> rows = session.query(cypher, Collections.<String, Object>emptyMap());
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("nodeCount", 0);
        stats.put("relationshipCount", 0);
        for (Map<String, Object> row : rows) {
            stats.put("nodeCount", row.get("nodeCount"));
            stats.put("relationshipCount", row.get("relationshipCount"));
            break;
        }

        String entityCountCypher =
                "MATCH (node) UNWIND labels(node) AS label " +
                "RETURN label, count(node) AS count ORDER BY count DESC";
        Map<String, Object> entityCounts = new LinkedHashMap<>();
        for (Map<String, Object> row : session.query(entityCountCypher, Collections.<String, Object>emptyMap())) {
            entityCounts.put(String.valueOf(row.get("label")), row.get("count"));
        }
        stats.put("entityCounts", entityCounts);

        String coverageCypher =
                "MATCH (registration:RegisterNumber) RETURN " +
                "count(registration) AS registrationCount, " +
                "sum(CASE WHEN registration.`Member State of origin` = 'China' THEN 1 ELSE 0 END) AS chinaCount, " +
                "sum(CASE WHEN registration.Status IS NOT NULL THEN 1 ELSE 0 END) AS germanyCount, " +
                "sum(CASE WHEN registration.`Approval number/Member State of origin` IS NOT NULL THEN 1 ELSE 0 END) AS euMutualRecognitionCount, " +
                "sum(CASE WHEN registration.`Member State of origin` IS NULL AND registration.Status IS NULL THEN 1 ELSE 0 END) AS unclassifiedCount";
        for (Map<String, Object> row : session.query(coverageCypher, Collections.<String, Object>emptyMap())) {
            stats.put("registrationCount", row.get("registrationCount"));
            Map<String, Object> datasets = new LinkedHashMap<>();
            datasets.put("china", row.get("chinaCount"));
            datasets.put("germany", row.get("germanyCount"));
            datasets.put("euMutualRecognition", row.get("euMutualRecognitionCount"));
            datasets.put("unclassified", row.get("unclassifiedCount"));
            stats.put("datasets", datasets);
            break;
        }

        String jurisdictionCypher =
                "MATCH (registration:RegisterNumber) " +
                "WITH trim(toString(registration.`Member State of origin`)) AS jurisdiction " +
                "WHERE jurisdiction <> '' AND jurisdiction <> '-' " +
                "RETURN collect(DISTINCT jurisdiction) AS jurisdictions";
        for (Map<String, Object> row : session.query(jurisdictionCypher, Collections.<String, Object>emptyMap())) {
            stats.put("jurisdictions", row.get("jurisdictions"));
            break;
        }
        return stats;
    }

    private Map<String, Object> executeGraphQuery(
            Session session,
            String cypher,
            Map<String, Object> parameters,
            String keyword
    ) {
        Iterable<Map<String, Object>> rows = session.query(cypher, parameters);
        Map<Long, Map<String, Object>> nodesById = new LinkedHashMap<>();
        List<Map<String, Object>> edges = new ArrayList<>();
        Set<String> edgeKeys = new LinkedHashSet<>();
        Long centerId = null;

        for (Map<String, Object> row : rows) {
            Long rowCenterId = asLong(row.get("centerId"));
            if (rowCenterId == null) continue;
            if (centerId == null) centerId = rowCenterId;

            putNode(nodesById, rowCenterId, row.get("centerLabel"), row.get("centerProperties"), true);
            Long neighborId = asLong(row.get("neighborId"));
            if (neighborId == null) continue;

            putNode(nodesById, neighborId, row.get("neighborLabel"), row.get("neighborProperties"), false);
            String relationType = safeText(row.get("relationType"), "RELATED_TO");
            Long relationSourceId = asLong(row.get("relationSourceId"));
            Long relationTargetId = asLong(row.get("relationTargetId"));
            if (relationSourceId == null || relationTargetId == null) {
                relationSourceId = rowCenterId;
                relationTargetId = neighborId;
            }
            String edgeKey = relationSourceId + ":" + relationTargetId + ":" + relationType;
            if (edgeKeys.add(edgeKey)) {
                Map<String, Object> edge = new LinkedHashMap<>();
                edge.put("source", relationSourceId);
                edge.put("target", relationTargetId);
                edge.put("type", relationType);
                edges.add(edge);
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("keyword", keyword);
        result.put("found", centerId != null);
        result.put("centerId", centerId);
        result.put("nodes", new ArrayList<>(nodesById.values()));
        result.put("edges", edges);
        result.put("nodeCount", nodesById.size());
        result.put("relationshipCount", edges.size());
        result.put("truncated", edges.size() >= MAX_NEIGHBORS);
        return result;
    }

    private Map<String, Object> executePathQuery(
            Session session,
            String cypher,
            Map<String, Object> parameters,
            String sourceKeyword,
            String targetKeyword
    ) {
        Iterable<Map<String, Object>> rows = session.query(cypher, parameters);
        Map<Long, Map<String, Object>> nodesById = new LinkedHashMap<>();
        List<Map<String, Object>> edges = new ArrayList<>();
        Long centerId = null;
        Long targetId = null;

        for (Map<String, Object> row : rows) {
            Long rowCenterId = asLong(row.get("centerId"));
            Long rowTargetId = asLong(row.get("targetId"));
            Long leftId = asLong(row.get("leftId"));
            Long rightId = asLong(row.get("rightId"));
            if (rowCenterId == null || rowTargetId == null || leftId == null || rightId == null) continue;
            if (centerId == null) centerId = rowCenterId;
            targetId = rowTargetId;

            putNode(
                    nodesById,
                    leftId,
                    row.get("leftLabel"),
                    row.get("leftProperties"),
                    leftId.equals(rowCenterId)
            );
            putNode(
                    nodesById,
                    rightId,
                    row.get("rightLabel"),
                    row.get("rightProperties"),
                    rightId.equals(rowCenterId)
            );

            Map<String, Object> edge = new LinkedHashMap<>();
            edge.put("source", leftId);
            edge.put("target", rightId);
            edge.put("type", safeText(row.get("relationType"), "RELATED_TO"));
            edges.add(edge);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("sourceKeyword", sourceKeyword);
        result.put("targetKeyword", targetKeyword);
        result.put("found", centerId != null && targetId != null);
        result.put("centerId", centerId);
        result.put("targetId", targetId);
        result.put("nodes", new ArrayList<>(nodesById.values()));
        result.put("edges", edges);
        result.put("nodeCount", nodesById.size());
        result.put("relationshipCount", edges.size());
        result.put("pathLength", edges.size());
        result.put("truncated", false);
        return result;
    }

    @SuppressWarnings("unchecked")
    private void putNode(
            Map<Long, Map<String, Object>> nodesById,
            Long id,
            Object labelValue,
            Object propertiesValue,
            boolean center
    ) {
        if (nodesById.containsKey(id)) return;
        Map<String, Object> rawProperties = propertiesValue instanceof Map
                ? (Map<String, Object>) propertiesValue
                : Collections.<String, Object>emptyMap();

        Map<String, Object> node = new LinkedHashMap<>();
        node.put("id", id);
        node.put("label", safeText(labelValue, "Entity"));
        node.put("name", nodeName(rawProperties));
        node.put("center", center);
        node.put("imageUrl", imageUrl(rawProperties));
        node.put("properties", selectProperties(rawProperties, center));
        node.put("evidence", evidenceMetadata(rawProperties, safeText(labelValue, "Entity")));
        nodesById.put(id, node);
    }

    private Map<String, Object> selectProperties(Map<String, Object> rawProperties, boolean center) {
        int limit = center ? MAX_CENTER_PROPERTIES : MAX_NEIGHBOR_PROPERTIES;
        Map<String, Object> selected = new LinkedHashMap<>();
        for (String property : IMPORTANT_PROPERTIES) {
            if (selected.size() >= limit) break;
            if (rawProperties.containsKey(property)) {
                addProperty(selected, property, rawProperties.get(property), limit);
            }
        }
        for (Map.Entry<String, Object> entry : rawProperties.entrySet()) {
            if (selected.size() >= limit) break;
            addProperty(selected, entry.getKey(), entry.getValue(), limit);
        }
        return selected;
    }

    private void addProperty(Map<String, Object> selected, String key, Object value, int limit) {
        if (selected.size() >= limit || selected.containsKey(key) || INTERNAL_PROPERTIES.contains(key) || value == null) return;
        String text = String.valueOf(value).trim();
        if (text.isEmpty() || text.matches("[-—–_\\s]+") || "null".equalsIgnoreCase(text)) return;
        if (text.length() > MAX_PROPERTY_LENGTH) {
            text = text.substring(0, MAX_PROPERTY_LENGTH) + "…";
        }
        selected.put(key, text);
    }

    private Map<String, Object> evidenceMetadata(Map<String, Object> properties, String label) {
        Map<String, Object> evidence = new LinkedHashMap<>();
        String jurisdiction = firstMeaningful(properties,
                "jurisdiction", "Member State of origin", "Jurisdiction", "country", "Country");
        boolean inferred = false;
        String dataset = null;

        if ("RegisterNumber".equals(label)) {
            if ("China".equalsIgnoreCase(jurisdiction) || hasMeaningful(properties, "Effect Type")) {
                jurisdiction = "China";
                dataset = "中国农药登记字段集";
            } else if (hasMeaningful(properties, "Status") && !hasMeaningful(properties, "Member State of origin")) {
                jurisdiction = "Germany";
                dataset = "德国植保登记字段集";
                inferred = true;
            } else if (hasMeaningful(properties, "Approval number/Member State of origin")) {
                dataset = "欧盟成员国互认字段集";
            } else {
                dataset = "待归档登记数据";
            }
        }

        putIfMeaningful(evidence, "dataset", dataset);
        putIfMeaningful(evidence, "jurisdiction", jurisdiction);
        putIfMeaningful(evidence, "status", firstMeaningful(properties,
                "Status", "Registration Status", "registration_status"));
        putIfMeaningful(evidence, "validUntil", firstMeaningful(properties,
                "valid_until", "End of approval", "Time expiry date_y", "valid until", "expiry_date"));
        putIfMeaningful(evidence, "sourceName", firstMeaningful(properties,
                "Source", "source", "source_name"));
        putIfMeaningful(evidence, "sourceUrl", firstHttpUrl(properties,
                "source_url", "original_url", "Source URL", "Original URL", "url"));
        putIfMeaningful(evidence, "collectedAt", firstMeaningful(properties,
                "collected_at", "crawl_time", "collectedAt", "采集时间"));
        putIfMeaningful(evidence, "updatedAt", firstMeaningful(properties,
                "updated_at", "updatedAt", "更新时间"));
        evidence.put("jurisdictionInferred", inferred);
        evidence.put("traceable", evidence.containsKey("sourceUrl") && evidence.containsKey("collectedAt"));
        return evidence;
    }

    private String firstMeaningful(Map<String, Object> properties, String... keys) {
        for (String key : keys) {
            Object value = properties.get(key);
            if (value == null) continue;
            String text = String.valueOf(value).trim();
            if (!text.isEmpty() && !text.matches("[-—–_\\s]+") && !"null".equalsIgnoreCase(text)) return text;
        }
        return null;
    }

    private boolean hasMeaningful(Map<String, Object> properties, String key) {
        return firstMeaningful(properties, key) != null;
    }

    private String firstHttpUrl(Map<String, Object> properties, String... keys) {
        String value = firstMeaningful(properties, keys);
        return value != null && value.matches("(?i)^https?://[^\\s]+$") ? value : null;
    }

    private void putIfMeaningful(Map<String, Object> target, String key, String value) {
        if (value != null && !value.trim().isEmpty()) target.put(key, value);
    }

    private String nodeName(Map<String, Object> properties) {
        Object name = properties.get("name");
        if (name != null && !String.valueOf(name).trim().isEmpty()) return String.valueOf(name);
        for (String property : IMPORTANT_PROPERTIES) {
            Object value = properties.get(property);
            if (value != null && !String.valueOf(value).trim().isEmpty()) return String.valueOf(value);
        }
        return "未命名实体";
    }

    private String imageUrl(Map<String, Object> properties) {
        for (Map.Entry<String, Object> entry : properties.entrySet()) {
            String key = entry.getKey() == null ? "" : entry.getKey().toLowerCase();
            if (!(key.contains("image") || key.contains("photo") || key.contains("picture") || key.contains("structure"))) {
                continue;
            }
            String value = entry.getValue() == null ? "" : String.valueOf(entry.getValue()).trim();
            if (value.matches("(?i)^https?://[^\\s]+$")) return value;
        }
        return null;
    }

    private Long asLong(Object value) {
        if (value instanceof Number) return ((Number) value).longValue();
        if (value == null) return null;
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private String safeText(Object value, String fallback) {
        if (value == null || String.valueOf(value).trim().isEmpty()) return fallback;
        return String.valueOf(value);
    }

    private String searchableText(String alias) {
        return "toLower(" +
                "coalesce(toString(" + alias + ".name), '') + ' ' + " +
                "coalesce(toString(" + alias + ".`Trade name`), '') + ' ' + " +
                "coalesce(toString(" + alias + ".`Pesticide name`), '') + ' ' + " +
                "coalesce(toString(" + alias + ".`Active Ingredient`), '') + ' ' + " +
                "coalesce(toString(" + alias + ".`CAS registry number`), '')" +
                ")";
    }

    private String primaryName(String alias) {
        return "coalesce(" +
                "toString(" + alias + ".name), " +
                "toString(" + alias + ".`Trade name`), " +
                "toString(" + alias + ".`Pesticide name`), " +
                "toString(" + alias + ".`Active Ingredient`), " +
                "toString(" + alias + ".`CAS registry number`), '')";
    }

    private String matchRank(String alias, String parameter) {
        String keyword = "toLower($" + parameter + ")";
        return "CASE " +
                "WHEN toLower(" + primaryName(alias) + ") = " + keyword + " THEN 0 " +
                "WHEN toLower(coalesce(toString(" + alias + ".`Trade name`), '')) = " + keyword + " THEN 1 " +
                "WHEN toLower(coalesce(toString(" + alias + ".`Pesticide name`), '')) = " + keyword + " THEN 1 " +
                "WHEN toLower(coalesce(toString(" + alias + ".`Active Ingredient`), '')) = " + keyword + " THEN 1 " +
                "WHEN toLower(coalesce(toString(" + alias + ".`CAS registry number`), '')) = " + keyword + " THEN 1 " +
                "WHEN toLower(" + primaryName(alias) + ") STARTS WITH " + keyword + " THEN 2 " +
                "ELSE 3 END";
    }
}
