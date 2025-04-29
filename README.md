# Kitchiin

![CI/CD Build Status](https://github.com/software-students-spring2025/5-final-stacked/actions/workflows/webapp.yml/badge.svg)

Our app is a pantry tracker where users can join households with their roommates. They can manage a shared grocery list, log pantry items, and track ownership. Users can also send requests to borrow items from their roommates.
[Link to our app](http://kitchiin.com/login)

## Docker Images

- [Web App Image on DockerHub](https://hub.docker.com/r/tony7892/kitchiin-web-app)

## Testing

Our application includes unit tests for backend services, achieving 85% code coverage using pytest.

## Team Members of Stacked

- [Harini Buddaluru](https://github.com/peanutoil)
- [Clarissa Choi](https://github.com/clammy424)
- [Franyel Diaz Rodriguez](https://github.com/Franyel1)
- [Tony Liu](https://github.com/tony102809)

## Setup Instructions to run Locally

### 1. Install Dependencies
```bash
# Install Python packages
pip install -r requirements.txt
```

### 2. Install Docker Desktop (if needed)

### 3. Create .env file
```bash
# .env.example
MONGO_URI=mongodb+srv://yourusername:yourpassword@yourcluster.mongodb.net/
MONGO_DBNAME=kitchiin
FLASK_PORT=5000
```
### 4. Run the Project
```bash
docker compose build
docker compose up
```
### 5. Access Application

Once the docker container is built, you can access the web app by entering the below into your browser:
http://localhost:5000