# Member 3 API Gateway Routes

## Query Lambda

Lambda folder:

backend/lambdas/queries/handler.py

Routes:

POST /query/tags
POST /query/species
POST /query/thumbnail
POST /query/file

Required environment variables:

DYNAMODB_TABLE
S3_BUCKET
GCP_FUNCTION_URL

---

## Tags Lambda

Lambda folder:

backend/lambdas/tags/handler.py

Route:

POST /tags

Required environment variables:

DYNAMODB_TABLE
SNS_TOPIC_ARN

---

## Delete Lambda

Lambda folder:

backend/lambdas/delete/handler.py

Route:

POST /delete

Required environment variables:

DYNAMODB_TABLE
S3_BUCKET

---

## Notifications Lambda

Lambda folder:

backend/lambdas/notifications/handler.py

Routes:

POST /notifications/subscribe
POST /notifications/unsubscribe

Required environment variables:

DYNAMODB_TABLE
SNS_TOPIC_ARN

---

## Notes

All routes must later be protected using Cognito authorisation.

The frontend should call these endpoints only after the user has logged in successfully.
