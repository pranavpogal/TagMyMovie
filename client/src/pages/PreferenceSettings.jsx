import { Alert, Box, CircularProgress, Toolbar } from "@mui/material";
import { useEffect, useState } from "react";
import userApi from "../api/modules/user.api";
import Container from "../components/common/Container";
import PreferenceEditor from "../components/common/PreferenceEditor";
import uiConfigs from "../configs/ui.configs";

const PreferenceSettings = () => {
  const [preferences, setPreferences] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    userApi.getPreferences().then(({ response }) => {
      if (response) setPreferences(response);
      else setError(true);
    });
  }, []);

  return (
    <>
      <Toolbar />
      <Box sx={{ ...uiConfigs.style.mainContent }}>
        <Container header="Recommendation preferences">
          {error && <Alert severity="error">Could not load your preferences.</Alert>}
          {!error && !preferences && <CircularProgress />}
          {preferences && <PreferenceEditor initialPreferences={preferences} onSaved={setPreferences} />}
        </Container>
      </Box>
    </>
  );
};

export default PreferenceSettings;
