package com.example.insecurejava;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;
import java.io.ObjectInputFilter;
import java.io.InvalidClassException;

@RestController
public class UnsafeDeserializationController {

    @PostMapping("/unsafeDeserialize")
    public ResponseEntity<String> unsafeDeserialization(@RequestBody byte[] data) {
        if (data == null || data.length == 0) {
            return ResponseEntity.badRequest().body("No data provided");
        }
        // Reject overly large payloads to prevent resource exhaustion
        final int MAX_PAYLOAD = 64 * 1024; // 64 KB
        if (data.length > MAX_PAYLOAD) {
            return ResponseEntity.status(HttpStatus.PAYLOAD_TOO_LARGE).body("Payload too large");
        }

        try (ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(data))) {
            // Apply a strict ObjectInputFilter allowlist and limits (including array/byte limits)
            String filterSpec = "maxdepth=10;maxrefs=100;maxarray=65536;maxbytes=65536;" +
                    "java.lang.String;" +
                    "java.lang.Integer;java.lang.Long;java.lang.Short;java.lang.Byte;java.lang.Double;java.lang.Float;" +
                    "java.lang.Boolean;[B;!*";
            ObjectInputFilter filter = ObjectInputFilter.Config.createFilter(filterSpec);
            ois.setObjectInputFilter(filter);

            Object deserializedObject = ois.readObject();

            // Only allow simple scalar types and byte[]; reject others
            if (!(deserializedObject instanceof String ||
                    deserializedObject instanceof Number ||
                    deserializedObject instanceof Boolean ||
                    deserializedObject instanceof byte[])) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body("Deserialized object type not allowed");
            }

            // Extra application-level size checks after deserialization
            if (deserializedObject instanceof String) {
                String s = (String) deserializedObject;
                if (s.length() > 4096) {
                    return ResponseEntity.status(HttpStatus.BAD_REQUEST).body("Deserialized String too large");
                }
            }
            if (deserializedObject instanceof byte[]) {
                byte[] b = (byte[]) deserializedObject;
                if (b.length > MAX_PAYLOAD) {
                    return ResponseEntity.status(HttpStatus.BAD_REQUEST).body("Deserialized byte[] too large");
                }
            }

            return ResponseEntity.ok("Object deserialized: " + deserializedObject.toString());
        } catch (InvalidClassException e) {
            // Expected when the filter rejects a type
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body("Deserialization rejected: " + e.getMessage());
        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body("Error during deserialization");
        }
    }
}
