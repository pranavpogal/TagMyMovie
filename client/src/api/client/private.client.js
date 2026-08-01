import axios from "axios";
import queryString from "query-string";
import apiConfigs from "../configs/api.configs";

const privateClient = axios.create({
  baseURL: apiConfigs.baseUrl,
  paramsSerializer: {
    encode: (params) => queryString.stringify(params),
  },
});

privateClient.interceptors.request.use(async (config) => {
  return {
    ...config,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${localStorage.getItem("actkn")}`,
    },
  };
});

privateClient.interceptors.response.use(
  (response) => {
    if (response && response.data) return response.data;
    return response;
  },
  (err) => {
    throw err.response ? err.response.data : err;
  }
);

export default privateClient;
