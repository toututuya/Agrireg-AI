package com.sc.pesticideknowledgemappingsystem.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

class GraphEvidenceSelectionTest {
    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void rendersOnlyValidReferencesAndUsesGraphValues() throws Exception {
        Map<Integer, String> facts = GraphEvidenceSelection.format(Arrays.asList(
                registrationFact(1, "PD-A", "水稻"), registrationFact(2, "PD-B", "玉米")));
        JsonNode selection = mapper.readTree("{\"evidenceIndices\":[2,99,2,\"1\",1.8],\"answer\":\"PD-A 登记了玉米\"}");

        assertEquals("PD-B — REGISTERED_FOR → 玉米 [2]", GraphEvidenceSelection.render(selection, facts));
    }

    @Test
    void declinesWhenAllReferencesAreMissingOrInvalid() throws Exception {
        Map<Integer, String> facts = GraphEvidenceSelection.format(Collections.singletonList(
                registrationFact(1, "PD-A", "水稻")));
        assertEquals("", GraphEvidenceSelection.render(mapper.readTree("{\"evidenceIndices\":[0,8]}"), facts));
        assertEquals("", GraphEvidenceSelection.render(mapper.readTree("{\"answer\":\"无法引用\"}"), facts));
    }

    @Test
    void evidenceTextCannotIntroduceAdditionalCitationNumbers() throws Exception {
        Map<Integer, String> facts = GraphEvidenceSelection.format(Collections.singletonList(
                registrationFact(1, "PD-A", "水稻 [20]")));
        String answer = GraphEvidenceSelection.render(mapper.readTree("{\"evidenceIndices\":[1]}"), facts);
        assertFalse(answer.contains("[20]"));
        assertEquals("PD-A — REGISTERED_FOR → 水稻 ［20］ [1]", answer);
    }

    private Map<String, Object> registrationFact(int index, String registration, String crop) {
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("index", index);
        fact.put("factType", "relationship");
        fact.put("sourceName", registration);
        fact.put("relation", "REGISTERED_FOR");
        fact.put("targetName", crop);
        return fact;
    }
}
