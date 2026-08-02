import privateClient from "../client/private.client";
import publicClient from "../client/public.client";

const userEndpoints = {
  signin: "user/signin",
  signup: "user/signup",
  getInfo: "user/info",
  passwordUpdate: "user/update-password",
  preferences: "user/preferences",
};

const userApi = {
  signin: async ({ username, password }) => {
    try {
      console.log("send request");
      const response = await publicClient.post(userEndpoints.signin, {
        username,
        password,
      });

      return { response };
    } catch (err) {
      console.log("err");
      return { err };
    }
  },
  signup: async ({ username, password, confirmPassword, displayName }) => {
    try {
      const response = await publicClient.post(userEndpoints.signup, {
        username,
        password,
        confirmPassword,
        displayName,
      });

      return { response };
    } catch (err) {
      return { err };
    }
  },
  getInfo: async () => {
    try {
      const response = await privateClient.get(userEndpoints.getInfo);

      return { response };
    } catch (err) {
      return { err };
    }
  },
  passwordUpdate: async ({ password, newPassword, confirmNewPassword }) => {
    try {
      const response = await privateClient.put(userEndpoints.passwordUpdate, {
        password,
        newPassword,
        confirmNewPassword,
      });

      return { response };
    } catch (err) {
      return { err };
    }
  },
  getPreferences: async () => {
    try {
      const response = await privateClient.get(userEndpoints.preferences);
      return { response };
    } catch (err) {
      return { err };
    }
  },
  updatePreferences: async (preferences) => {
    try {
      const response = await privateClient.put(userEndpoints.preferences, preferences);
      return { response };
    } catch (err) {
      return { err };
    }
  },
};

export default userApi;
