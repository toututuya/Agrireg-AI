package com.sc.pesticideknowledgemappingsystem.controller;

import com.sc.pesticideknowledgemappingsystem.service.GraphExploreService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/graph")
@CrossOrigin(origins = "${APP_CORS_ALLOWED_ORIGIN:http://127.0.0.1:8082}")
public class GraphExploreController {

    @Autowired
    private GraphExploreService graphExploreService;

    @GetMapping("/search")
    public ResponseEntity<Map<String, Object>> search(@RequestParam("keyword") String keyword) {
        String normalized = keyword == null ? "" : keyword.trim();
        if (!validKeyword(normalized)) {
            return error(HttpStatus.BAD_REQUEST, "请输入 1–80 个字符的实体名称。");
        }
        try {
            return ResponseEntity.ok(graphExploreService.search(normalized));
        } catch (Exception exception) {
            return error(HttpStatus.SERVICE_UNAVAILABLE, "暂时无法读取关系数据，请稍后再试。");
        }
    }

    @GetMapping("/node/{nodeId}")
    public ResponseEntity<Map<String, Object>> explore(@PathVariable("nodeId") long nodeId) {
        if (nodeId < 0) return error(HttpStatus.BAD_REQUEST, "节点编号无效。");
        try {
            return ResponseEntity.ok(graphExploreService.explore(nodeId));
        } catch (Exception exception) {
            return error(HttpStatus.SERVICE_UNAVAILABLE, "暂时无法读取关系数据，请稍后再试。");
        }
    }

    @GetMapping("/path")
    public ResponseEntity<Map<String, Object>> path(
            @RequestParam("source") String source,
            @RequestParam("target") String target
    ) {
        String normalizedSource = source == null ? "" : source.trim();
        String normalizedTarget = target == null ? "" : target.trim();
        if (!validKeyword(normalizedSource) || !validKeyword(normalizedTarget)) {
            return error(HttpStatus.BAD_REQUEST, "请输入 1–80 个字符的起点和终点实体名称。");
        }
        if (normalizedSource.equalsIgnoreCase(normalizedTarget)) {
            return error(HttpStatus.BAD_REQUEST, "起点和终点需要是不同的实体。");
        }
        try {
            return ResponseEntity.ok(graphExploreService.findPath(normalizedSource, normalizedTarget));
        } catch (Exception exception) {
            return error(HttpStatus.SERVICE_UNAVAILABLE, "暂时无法分析关联路径，请稍后再试。");
        }
    }

    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> stats() {
        try {
            return ResponseEntity.ok(graphExploreService.stats());
        } catch (Exception exception) {
            return error(HttpStatus.SERVICE_UNAVAILABLE, "暂时无法读取图谱信息，请稍后再试。");
        }
    }

    private ResponseEntity<Map<String, Object>> error(HttpStatus status, String message) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("status", status.value());
        payload.put("message", message);
        return ResponseEntity.status(status).body(payload);
    }

    private boolean validKeyword(String keyword) {
        return keyword.length() >= 1 && keyword.length() <= 80;
    }
}
