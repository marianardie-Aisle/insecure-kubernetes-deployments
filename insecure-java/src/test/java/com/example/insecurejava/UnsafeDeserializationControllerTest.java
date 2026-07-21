package com.example.insecurejava;

import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.util.Date;

import static org.junit.jupiter.api.Assertions.*;

class UnsafeDeserializationControllerTest {

    @Test
    void testSafeStringDeserialization() throws Exception {
        String payload = "hello";
        byte[] data;
        try (ByteArrayOutputStream bos = new ByteArrayOutputStream();
             ObjectOutputStream oos = new ObjectOutputStream(bos)) {
            oos.writeObject(payload);
            oos.flush();
            data = bos.toByteArray();
        }

        UnsafeDeserializationController controller = new UnsafeDeserializationController();
        ResponseEntity<String> response = controller.unsafeDeserialization(data);
        assertEquals(200, response.getStatusCodeValue());
        assertTrue(response.getBody().contains("hello"));
    }

    @Test
    void testRejectedTypeDeserialization() throws Exception {
        Date payload = new Date();
        byte[] data;
        try (ByteArrayOutputStream bos = new ByteArrayOutputStream();
             ObjectOutputStream oos = new ObjectOutputStream(bos)) {
            oos.writeObject(payload);
            oos.flush();
            data = bos.toByteArray();
        }

        UnsafeDeserializationController controller = new UnsafeDeserializationController();
        ResponseEntity<String> response = controller.unsafeDeserialization(data);
        assertEquals(400, response.getStatusCodeValue());
    }
}
