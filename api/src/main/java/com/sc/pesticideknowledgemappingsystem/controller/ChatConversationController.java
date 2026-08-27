package com.sc.pesticideknowledgemappingsystem.controller;

import com.sc.pesticideknowledgemappingsystem.service.ChatConversationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/conversations")
@CrossOrigin(origins = "${APP_CORS_ALLOWED_ORIGIN:http://127.0.0.1:8082}")
public class ChatConversationController {

    @Autowired
    private ChatConversationService conversationService;

    @GetMapping
    public List<Map<String, Object>> list(
            @RequestParam(value = "visitorId", defaultValue = "local-demo") String visitorId
    ) {
        return conversationService.list(visitorId);
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(
            @PathVariable("id") String id,
            @RequestParam(value = "visitorId", defaultValue = "local-demo") String visitorId
    ) {
        try {
            return ResponseEntity.ok(conversationService.get(visitorId, id));
        } catch (IllegalArgumentException exception) {
            return ResponseEntity.notFound().build();
        }
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(
            @PathVariable("id") String id,
            @RequestParam(value = "visitorId", defaultValue = "local-demo") String visitorId
    ) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("deleted", conversationService.delete(visitorId, id));
        return result;
    }
}
