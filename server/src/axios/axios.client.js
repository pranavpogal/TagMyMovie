import axios from "axios";

const get = async (url) => {
  const response = await axios.get(url, {
    timeout: 10000,
    headers: {
      Accept: "application/json",
      "Accept-Encoding": "identity",
    },
  });
  return response.data;
};

export default { get };
