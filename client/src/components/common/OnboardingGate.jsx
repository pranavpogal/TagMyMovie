import { Dialog, DialogContent, DialogTitle } from "@mui/material";
import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import userApi from "../../api/modules/user.api";
import PreferenceEditor from "./PreferenceEditor";

const OnboardingGate = () => {
  const { user } = useSelector((state) => state.user);
  const [preferences, setPreferences] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let active = true;
    if (!user) {
      setOpen(false);
      setPreferences(null);
      return () => { active = false; };
    }
    userApi.getPreferences().then(({ response }) => {
      if (!active || !response) return;
      setPreferences(response);
      setOpen(!response.onboardingCompleted && !response.onboardingSkipped);
    });
    return () => { active = false; };
  }, [user]);

  return (
    <Dialog open={open} maxWidth="md" fullWidth disableEscapeKeyDown>
      <DialogTitle>Tell us what you like</DialogTitle>
      <DialogContent>
        {preferences && <PreferenceEditor initialPreferences={preferences} onboarding onSaved={() => setOpen(false)} onSkipped={() => setOpen(false)} />}
      </DialogContent>
    </Dialog>
  );
};

export default OnboardingGate;
