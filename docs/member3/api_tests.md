# Member 3 API Test Documentation

## Overview

This document describes the request and response formats used to test the Member 3 APIs:

* Query by tags
* Query by species
* Query by thumbnail URL
* Query by uploaded file
* Add tags
* Remove tags
* Delete files
* Subscribe to notifications
* Unsubscribe from notifications

---

# 1. Query Files by Tags and Counts

### Endpoint

```http
POST /query/tags
```

### Request

```json
{
  "tags": {
    "koala": 3,
    "wombat": 1
  }
}
```

### Expected Response

```json
{
  "count": 1,
  "results": [
    {
      "file_id": "file001",
      "file_url": "https://example.com/uploads/koala.jpg",
      "thumbnail_url": "https://example.com/thumbnails/koala.jpg",
      "file_type": "image",
      "tags": {
        "koala": 3,
        "wombat": 1
      }
    }
  ]
}
```

---

# 2. Query Files by Species

### Endpoint

```http
POST /query/species
```

### Request

```json
{
  "species": "dingo"
}
```

### Expected Response

```json
{
  "count": 1,
  "results": [
    {
      "file_id": "file002",
      "file_url": "https://example.com/uploads/dingo.jpg",
      "thumbnail_url": "https://example.com/thumbnails/dingo.jpg",
      "file_type": "image",
      "tags": {
        "dingo": 1
      }
    }
  ]
}
```

---

# 3. Query Full Image from Thumbnail URL

### Endpoint

```http
POST /query/thumbnail
```

### Request

```json
{
  "thumbnail_url": "https://example.com/thumbnails/koala.jpg"
}
```

### Expected Response

```json
{
  "file_id": "file001",
  "file_url": "https://example.com/uploads/koala.jpg",
  "thumbnail_url": "https://example.com/thumbnails/koala.jpg",
  "tags": {
    "koala": 3,
    "wombat": 1
  }
}
```

---

# 4. Query Files Using an Uploaded File

### Endpoint

```http
POST /query/file
```

### Request

```json
{
  "file_base64": "BASE64_ENCODED_FILE",
  "content_type": "image/jpeg",
  "filename": "query.jpg"
}
```

### Expected Response

```json
{
  "detected_tags": [
    "koala"
  ],
  "count": 1,
  "results": [
    {
      "file_url": "https://example.com/uploads/koala.jpg",
      "thumbnail_url": "https://example.com/thumbnails/koala.jpg",
      "file_type": "image"
    }
  ]
}
```

---

# 5. Add Tags to Files

### Endpoint

```http
POST /tags
```

### Request

```json
{
  "urls": [
    "https://example.com/uploads/koala.jpg"
  ],
  "tags": [
    "kangaroo"
  ],
  "operation": 1
}
```

### Expected Response

```json
{
  "updated": [
    {
      "url": "https://example.com/uploads/koala.jpg"
    }
  ],
  "errors": [],
  "message": "Operation add completed"
}
```

---

# 6. Remove Tags from Files

### Endpoint

```http
POST /tags
```

### Request

```json
{
  "urls": [
    "https://example.com/uploads/koala.jpg"
  ],
  "tags": [
    "wombat"
  ],
  "operation": 0
}
```

### Expected Response

```json
{
  "updated": [
    {
      "url": "https://example.com/uploads/koala.jpg"
    }
  ],
  "errors": [],
  "message": "Operation remove completed"
}
```

---

# 7. Delete Files

### Endpoint

```http
POST /delete
```

### Request

```json
{
  "urls": [
    "https://example.com/uploads/koala.jpg"
  ]
}
```

### Expected Response

```json
{
  "deleted": [
    {
      "url": "https://example.com/uploads/koala.jpg"
    }
  ],
  "errors": [],
  "message": "Deleted 1 file(s)"
}
```

---

# 8. Subscribe to Tag Notifications

### Endpoint

```http
POST /notifications/subscribe
```

### Request

```json
{
  "email": "student@example.com",
  "tags": [
    "koala"
  ]
}
```

### Expected Response

```json
{
  "message": "Subscription pending email confirmation for student@example.com",
  "subscription_arn": "arn:aws:sns:region:account:subscription-id",
  "watched_tags": [
    "koala"
  ]
}
```

---

# 9. Unsubscribe from Notifications

### Endpoint

```http
POST /notifications/unsubscribe
```

### Request

```json
{
  "subscription_arn": "arn:aws:sns:region:account:subscription-id"
}
```

### Expected Response

```json
{
  "message": "Unsubscribed successfully"
}
```

---

# Testing Notes

* Query file uploads are temporary and are deleted after processing.
* Search by tags uses AND logic.
* Search by species requires at least one occurrence of the species.
* Tag updates support bulk operations.
* File deletion removes media files, thumbnails, video frame thumbnails, and associated DynamoDB records.
* SNS email subscriptions require email confirmation before notifications are delivered.
