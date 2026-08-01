const developmentBaseUrl = "http://localhost:5001/api/v1/";
const productionBaseUrl = "/api/v1/";

const configuredBaseUrl = process.env.REACT_APP_API_BASE_URL?.trim();

const baseUrl = configuredBaseUrl
  ? `${configuredBaseUrl.replace(/\/+$/, "")}/`
  : process.env.NODE_ENV === "development"
  ? developmentBaseUrl
  : productionBaseUrl;

const apiConfigs = { baseUrl };

export default apiConfigs;
