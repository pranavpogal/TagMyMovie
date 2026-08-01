import axios from "axios";
import queryString from "query-string";
import apiConfigs from "../configs/api.configs";

const publicClient = axios.create({
  baseURL: apiConfigs.baseUrl,
  paramsSerializer: {
    encode: (params) => queryString.stringify(params),
  },
});

publicClient.interceptors.request.use(async (config) => {
  return {
    ...config,
    headers: {
      "Content-Type": "application/json",
    },
  };
});

publicClient.interceptors.response.use(
  (response) => {
    if (response && response.data) return response.data;
    return response;
  },
  (err) => {
    throw err.response ? err.response.data : err;
  }
);

export default publicClient;
