# API Documentation

## Base URL

http://<host>:10694

---

## POST /redact

Redacts sensitive network data from input text.

### Request Body

{
  "text": "string"
}

### Response

{
  "mapping_id": "uuid",
  "redacted_text": "string",
  "mapping_count": 12
}

---

## GET /health

Returns service health status.

Response:

{
  "status": "ok"
}

---

## Error Handling

400 – Invalid input  
413 – Payload too large  
500 – Internal server error  

---

## Input Limits

- Maximum payload size: 1MB (recommended)
- Plain text only
- No file uploads

---

## Supported Redactions

- IPv4
- IPv6
- MAC addresses

---

## Example

```
Input:
Interface Ethernet1/1
IP address 192.168.1.10
MAC 00:11:22:33:44:55
Output
Interface Ethernet1/1
IP address 82.17.201.3
MAC a1:b2:c3:d4:e5:f6
```