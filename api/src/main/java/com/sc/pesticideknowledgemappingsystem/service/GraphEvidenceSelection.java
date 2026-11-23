package com.sc.pesticideknowledgemappingsystem.service;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.StringJoiner;

final class GraphEvidenceSelection {
    private static final int MAX_SELECTED = 12;

    private GraphEvidenceSelection() {
    }

    static Map<Integer, String> format(List<Map<String, Object>> evidence) {
        Map<Integer, String> formatted = new LinkedHashMap<>();
        for (Map<String, Object> fact : evidence) {
            Object index = fact.get("index");
            String source = literal(fact.get("sourceName"));
            boolean attribute = "attribute".equals(fact.get("factType"));
            String predicate = literal(fact.get(attribute ? "property" : "relation"));
            String value = literal(fact.get(attribute ? "value" : "targetName"));
            if (!(index instanceof Integer) || (Integer) index < 1 || source.isEmpty()
                    || predicate.isEmpty() || value.isEmpty()) continue;
            String separator = attribute ? " 的 " : " — ";
            String connector = attribute ? "：" : " → ";
            formatted.put((Integer) index, source + separator + predicate + connector + value);
        }
        return formatted;
    }

    static String render(JsonNode selection, Map<Integer, String> facts) {
        if (selection == null || !selection.path("evidenceIndices").isArray()) return "";
        Set<Integer> selected = new LinkedHashSet<>();
        for (JsonNode node : selection.path("evidenceIndices")) {
            if (!node.isIntegralNumber() || !node.canConvertToInt()) continue;
            int index = node.intValue();
            if (facts.containsKey(index)) selected.add(index);
            if (selected.size() == MAX_SELECTED) break;
        }
        StringJoiner answer = new StringJoiner("\n");
        for (Integer index : selected) answer.add(facts.get(index) + " [" + index + "]");
        return answer.toString();
    }

    private static String literal(Object value) {
        if (value == null) return "";
        return String.valueOf(value).replaceAll("[\\r\\n]+", " ").replace('[', '［').replace(']', '］').trim();
    }
}
