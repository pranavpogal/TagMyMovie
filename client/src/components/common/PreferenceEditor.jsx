import { LoadingButton } from "@mui/lab";
import { Alert, Autocomplete, Box, Button, Chip, FormControl, InputLabel, MenuItem, Select, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import genreApi from "../../api/modules/genre.api";
import mediaApi from "../../api/modules/media.api";
import userApi from "../../api/modules/user.api";

const languageOptions = [
  { code: "en", label: "English" }, { code: "hi", label: "Hindi" },
  { code: "mr", label: "Marathi" }, { code: "ta", label: "Tamil" },
  { code: "te", label: "Telugu" }, { code: "bn", label: "Bengali" },
  { code: "es", label: "Spanish" }, { code: "fr", label: "French" },
  { code: "de", label: "German" }, { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
];
const releaseOptions = ["pre_1980", "1980s", "1990s", "2000s", "2010s", "2020s"];

const PreferenceEditor = ({ initialPreferences = {}, onboarding = false, onSaved, onSkipped }) => {
  const [genres, setGenres] = useState([]);
  const [genreIds, setGenreIds] = useState(initialPreferences.preferredGenreIds || []);
  const [languages, setLanguages] = useState(initialPreferences.preferredLanguages || []);
  const [releasePeriods, setReleasePeriods] = useState(initialPreferences.preferredReleasePeriods || []);
  const [seeds, setSeeds] = useState(initialPreferences.favouriteSeedMedia || []);
  const [seedType, setSeedType] = useState("movie");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([genreApi.getList({ mediaType: "movie" }), genreApi.getList({ mediaType: "tv" })]).then((responses) => {
      const merged = new Map();
      responses.forEach(({ response }) => (response?.genres || []).forEach((genre) => merged.set(genre.id, genre)));
      setGenres([...merged.values()].sort((a, b) => a.name.localeCompare(b.name)));
    });
  }, []);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    const { response, err } = await mediaApi.search({ mediaType: seedType, query: query.trim(), page: 1 });
    setSearching(false);
    if (err) return toast.error("Could not search titles");
    setResults((response?.results || []).slice(0, 8));
  };

  const addSeed = (media) => {
    const key = `${seedType}:${media.id}`;
    if (seeds.some((seed) => `${seed.mediaType}:${seed.mediaId}` === key)) return;
    setSeeds((current) => [...current, {
      mediaId: String(media.id), mediaType: seedType,
      title: media.title || media.name, posterPath: media.poster_path || "",
    }]);
  };

  const save = async () => {
    if (genreIds.length < 3) return toast.error("Choose at least three genres");
    if (!languages.length) return toast.error("Choose at least one language");
    if (seeds.length < 3) return toast.error("Choose at least three favourite titles");
    setSaving(true);
    const { response, err } = await userApi.updatePreferences({
      preferredGenreIds: genreIds,
      preferredLanguages: languages,
      favouriteSeedMedia: seeds,
      preferredReleasePeriods: releasePeriods,
      onboardingCompleted: true,
    });
    setSaving(false);
    if (err) return toast.error(err.message || "Could not save preferences");
    toast.success("Recommendation preferences saved");
    onSaved?.(response);
  };

  const skip = async () => {
    setSaving(true);
    const { response, err } = await userApi.updatePreferences({ onboardingSkipped: true });
    setSaving(false);
    if (err) return toast.error(err.message || "Could not skip onboarding");
    onSkipped?.(response);
  };

  return (
    <Stack spacing={3}>
      <Alert severity="info">Your choices personalize recommendations and can be edited later.</Alert>
      <Autocomplete multiple options={genres} getOptionLabel={(option) => option.name}
        value={genres.filter((genre) => genreIds.includes(genre.id))}
        onChange={(_, value) => setGenreIds(value.map((genre) => genre.id))}
        renderInput={(params) => <TextField {...params} label="Favourite genres (at least 3)" />} />
      <Autocomplete multiple options={languageOptions} getOptionLabel={(option) => option.label}
        value={languageOptions.filter((language) => languages.includes(language.code))}
        onChange={(_, value) => setLanguages(value.map((language) => language.code))}
        renderInput={(params) => <TextField {...params} label="Preferred languages" />} />
      <Autocomplete multiple options={releaseOptions} value={releasePeriods}
        onChange={(_, value) => setReleasePeriods(value)}
        renderInput={(params) => <TextField {...params} label="Release periods (optional)" />} />
      <Box>
        <Typography variant="h6" gutterBottom>Favourite seed titles (at least 3)</Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <FormControl sx={{ minWidth: 120 }}><InputLabel>Type</InputLabel><Select value={seedType} label="Type" onChange={(event) => setSeedType(event.target.value)}><MenuItem value="movie">Movie</MenuItem><MenuItem value="tv">TV</MenuItem></Select></FormControl>
          <TextField fullWidth label="Search TMDB titles" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); search(); } }} />
          <LoadingButton variant="outlined" loading={searching} onClick={search}>Search</LoadingButton>
        </Stack>
        <Stack direction="row" flexWrap="wrap" gap={1} mt={2}>
          {results.map((media) => <Button key={media.id} size="small" variant="outlined" onClick={() => addSeed(media)}>+ {media.title || media.name}</Button>)}
        </Stack>
        <Stack direction="row" flexWrap="wrap" gap={1} mt={2}>
          {seeds.map((seed) => <Chip key={`${seed.mediaType}:${seed.mediaId}`} label={`${seed.title} (${seed.mediaType})`} onDelete={() => setSeeds((current) => current.filter((item) => item !== seed))} />)}
        </Stack>
      </Box>
      <Stack direction="row" justifyContent="flex-end" spacing={1}>
        {onboarding && <Button disabled={saving} onClick={skip}>Skip for now</Button>}
        <LoadingButton loading={saving} variant="contained" onClick={save}>Save preferences</LoadingButton>
      </Stack>
    </Stack>
  );
};

export default PreferenceEditor;
