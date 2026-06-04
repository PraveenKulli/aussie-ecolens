// src/aws-config.js
// Values are injected at build time from environment variables (set by Terraform outputs)
const awsConfig = {
  Auth: {
    Cognito: {
      userPoolId:       import.meta.env.VITE_COGNITO_USER_POOL_ID     || '',
      userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID        || '',
      signUpVerificationMethod: 'code',
    },
  },
};

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
export default awsConfig;
