# TagMyMovie: Movie Review Web Application

TagMyMovie is a dynamic movie review web application that empowers users to explore, review, and interact with their favorite movies and TV series. With a user-friendly interface and a wide array of features, TagMyMovie provides a comprehensive platform for cinephiles to engage with their passion.


## Features
- **Sign up / Sign in** : Users can create accounts or sign in to access personalized features.
- **Save movie to Favorite list** : Users can save their favorite movies, making it easy to keep track of must-watch films.
- **Write and Manage Movie Reviews** : Users can express their opinions by writing reviews for movies.
- **Search Functionality** : A robust search feature enables users to find movies, TV series, and people effortlessly.
- **Light and Dark Theme** : Users can toggle between a light and dark theme based on their visual preferences, enhancing the overall user experience.

## Tech Stack
- Frontend: Reactjs, Material UI, Redux(State Management) ,Swiper Js, Formik-Yup
- Backend: Node, Express, JWT
- API: TMDB
- Database: Mongoose(ODM), MongoDB
- API Communication: Axios

---
Explore, review, and engage with the world of movies and TV series through TagMyMovie. Create your account, share your thoughts, and dive into an immersive cinematic experience.

## Recommendation services

Authenticated clients use `GET /api/v1/recommendations` on the Express server. Express derives the user from the JWT, calls the private FastAPI service at `ML_SERVICE_URL`, validates its response, stores the recommendation impression, and returns the safe public payload. Start FastAPI on port 8000 before Express for ML results; Express automatically falls back to seed-title TMDB recommendations, explicit preferences, or popular content if ML is unavailable.
