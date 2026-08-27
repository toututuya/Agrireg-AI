package com.sc.pesticideknowledgemappingsystem.controller;

import com.sc.pesticideknowledgemappingsystem.service.DeepSeekGraphAssistantService;
import com.sc.pesticideknowledgemappingsystem.service.ChatConversationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/assistant")
@CrossOrigin(origins = "${APP_CORS_ALLOWED_ORIGIN:http://127.0.0.1:8082}")
public class GraphAssistantController {

    @Autowired
    private DeepSeekGraphAssistantService assistantService;

    @Autowired
    private ChatConversationService conversationService;

    @PostMapping("/ask")
    public ResponseEntity<Map<String, Object>> ask(@RequestBody Map<String, Object> request) {
        String question = request == null || request.get("question") == null
                ? ""
                : String.valueOf(request.get("question")).trim();
        String visitorId = stringValue(request, "visitorId");
        String conversationId = stringValue(request, "conversationId");
        if (question.length() < 2 || question.length() > 300) {
            return error(HttpStatus.BAD_REQUEST, "请输入 2–300 个字符的问题。", "INVALID_QUESTION");
        }
        if (!assistantService.isConfigured()) {
            return error(HttpStatus.SERVICE_UNAVAILABLE, "图谱智能问答暂未开放。", "ASSISTANT_UNAVAILABLE");
        }
        try {
            Map<String, Object> result = assistantService.ask(
                    question,
                    conversationService.recentContext(visitorId, conversationId)
            );
            if (Boolean.FALSE.equals(request.get("persist"))) {
                return ResponseEntity.ok(result);
            }
            Map<String, Object> conversation = conversationService.saveExchange(
                    visitorId, conversationId, question, result
            );
            result.put("conversationId", conversation.get("id"));
            result.put("conversationTitle", conversation.get("title"));
            return ResponseEntity.ok(result);
        } catch (IllegalArgumentException exception) {
            return error(HttpStatus.BAD_REQUEST, "没有找到这条对话，请新建对话后重试。", "CONVERSATION_NOT_FOUND");
        } catch (Exception exception) {
            return error(HttpStatus.BAD_GATEWAY, "这次回答没有生成成功，请稍后重试。", "ASSISTANT_REQUEST_FAILED");
        }
    }

    private String stringValue(Map<String, Object> request, String key) {
        if (request == null || request.get(key) == null) return "";
        return String.valueOf(request.get(key)).trim();
    }

    private ResponseEntity<Map<String, Object>> error(HttpStatus status, String message, String code) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("status", status.value());
        payload.put("code", code);
        payload.put("message", message);
        return ResponseEntity.status(status).body(payload);
    }
}
