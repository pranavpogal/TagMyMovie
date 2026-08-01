import privateClient from "../client/private.client";
import { getSessionId } from "../../utils/session.utils";

const interactionEndpoint = "interactions";

const interactionApi = {
  record: async (interaction) => {
    try {
      const response = await privateClient.post(interactionEndpoint, {
        ...interaction,
        sessionId: interaction.sessionId || getSessionId(),
      });
      return { response };
    } catch (err) {
      return { err };
    }
  },
};

export default interactionApi;
