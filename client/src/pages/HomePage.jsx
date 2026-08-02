import HeroSlide from "../components/common/HeroSlide"
import tmdbConfigs from "../api/configs/tmdb.configs"
import uiConfigs from "../configs/ui.configs"
import { Box } from "@mui/material"
import Container from "../components/common/Container"
import MediaSlide from "../components/common/MediaSlide"
import { useSelector } from "react-redux"
import PersonalizedRecommendations from "../components/common/PersonalizedRecommendations"

const HomePage = () => {
  const { user } = useSelector((state) => state.user)
  return (
    <>
      <HeroSlide mediaType={tmdbConfigs.mediaType.movie} mediaCategory={tmdbConfigs.mediaCategory.popular} />

      <Box marginTop="-4rem" sx={{...uiConfigs.style.mainContent }}>
        {user && (
          <Container header="Recommended for You">
            <PersonalizedRecommendations context="home" />
          </Container>
        )}
        <Container header="popular movies">
          <MediaSlide mediaType={tmdbConfigs.mediaType.movie} mediaCategory={tmdbConfigs.mediaCategory.popular}/>
        </Container>

        <Container header="popular series">
          <MediaSlide mediaType={tmdbConfigs.mediaType.tv} mediaCategory={tmdbConfigs.mediaCategory.popular}/>
        </Container>

        <Container header="top rated movies">
          <MediaSlide mediaType={tmdbConfigs.mediaType.movie} mediaCategory={tmdbConfigs.mediaCategory.top_rated}/>
        </Container>

        <Container header="top rated series">
          <MediaSlide mediaType={tmdbConfigs.mediaType.tv} mediaCategory={tmdbConfigs.mediaCategory.top_rated}/>
        </Container>
      </Box>
    </>
  )
}

export default HomePage
