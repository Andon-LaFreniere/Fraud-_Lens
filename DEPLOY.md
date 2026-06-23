# FraudLens — Deployment Guide

Two paths: **Local** (test it yourself in 15 min) and **AWS** (live public URL for recruiters).

---

## Part 1 — Run it locally

### Step 1 — Install prerequisites

Install these if you don't have them:

- **Docker Desktop** → https://www.docker.com/products/docker-desktop  
  *(Make sure Docker Desktop is open and running before continuing)*
- **Git** → already installed if you have GitHub

That's it. Java, Python, Node — none needed locally. Docker handles everything.

---

### Step 2 — Clone / open the project

If you downloaded the zip, unzip it and open a terminal in the `fraudlens/` folder.

```bash
cd fraudlens
```

---

### Step 3 — Start everything

```bash
docker-compose up --build
```

This will:
1. Pull Kafka, Zookeeper, and DynamoDB Local images (~2 min first run)
2. Build the Spring Boot JAR (~90 sec)
3. Build the Python service (~30 sec)
4. Build the React dashboard (~60 sec)
5. Start all 5 containers

You'll know it's ready when you see:
```
transaction-service  | Started FraudLensApplication in X seconds
fraud-scoring-service | Kafka consumer started, listening on topic: fraudlens.transactions
dashboard            | nginx started
```

---

### Step 4 — Open the dashboard

Go to: **http://localhost:3000**

You'll see the FraudLens dashboard with an empty alerts table.

---

### Step 5 — Submit a test transaction

**Option A — Use the dashboard form** (what a recruiter would do):
1. Click "Load high-risk example" to pre-fill a suspicious transaction
2. Click "Run Transaction →"
3. Wait ~2 seconds
4. Click "Refresh" — you'll see a CRITICAL or HIGH alert appear

**Option B — Use curl:**
```bash
# Suspicious transaction — should be flagged CRITICAL
curl -X POST http://localhost:8080/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "accountId": "ACC-001",
    "amount": 14500.00,
    "merchantCategory": "CRYPTO",
    "merchantCountry": "NG",
    "type": "WITHDRAWAL"
  }'

# Normal transaction — should not be flagged
curl -X POST http://localhost:8080/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "accountId": "ACC-002",
    "amount": 42.00,
    "merchantCategory": "GROCERY",
    "merchantCountry": "US",
    "type": "PURCHASE"
  }'

# Check alerts
curl http://localhost:8080/api/v1/alerts
```

---

### Step 6 — View API docs

Swagger UI: **http://localhost:8080/swagger-ui.html**  
Scoring service docs: **http://localhost:8001/docs**

---

### Step 7 — Stop everything

```bash
docker-compose down
```

---

## Part 2 — Deploy to AWS (public recruiter URL)

### Prerequisites

Install these:

```bash
# AWS CLI
# Mac:
brew install awscli
# Windows: https://aws.amazon.com/cli/ → download installer

# Terraform
# Mac:
brew tap hashicorp/tap && brew install hashicorp/tap/terraform
# Windows: https://developer.hashicorp.com/terraform/downloads
```

---

### Step 1 — Create a free AWS account

Go to https://aws.amazon.com and create an account.  
You'll need a credit card, but everything in this deployment fits in the **AWS Free Tier**.

---

### Step 2 — Create an IAM user for Terraform

1. Go to **AWS Console → IAM → Users → Create User**
2. Name it `fraudlens-deploy`
3. Select **Attach policies directly** → check `AdministratorAccess`
4. Click through to Create user
5. Click the user → **Security credentials** tab → **Create access key**
6. Choose **CLI** → download the CSV

---

### Step 3 — Configure AWS CLI

```bash
aws configure
```

Enter:
- AWS Access Key ID: (from the CSV)
- AWS Secret Access Key: (from the CSV)
- Default region: `us-east-1`
- Default output format: `json`

Verify it works:
```bash
aws sts get-caller-identity
```
You should see your account ID.

---

### Step 4 — Set up Amazon MSK (managed Kafka)

> MSK is the managed Kafka service. It takes ~15 min to provision.

1. Go to **AWS Console → Amazon MSK → Create cluster**
2. Choose **Quick create**
3. Cluster name: `fraudlens-kafka`
4. Broker type: `kafka.t3.small`
5. Click **Create cluster** and wait (~15 min)
6. Once active, click the cluster → **View client information** → copy the **Plaintext** bootstrap server string

It looks like: `b-1.fraudleneskafka.xxxxx.c2.kafka.us-east-1.amazonaws.com:9092`

Save this — you'll need it in the next step.

---

### Step 5 — Build and push Docker images to ECR

```bash
# Get your AWS account ID
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

# Create ECR repos
aws ecr create-repository --repository-name fraudlens-transaction-service
aws ecr create-repository --repository-name fraudlens-scorer
aws ecr create-repository --repository-name fraudlens-dashboard

# Log Docker into ECR
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com

# Build and push transaction-service
cd transaction-service
docker build -t fraudlens-transaction-service .
docker tag fraudlens-transaction-service:latest $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/fraudlens-transaction-service:latest
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/fraudlens-transaction-service:latest
cd ..

# Build and push fraud-scoring-service
cd fraud-scoring-service
docker build -t fraudlens-scorer .
docker tag fraudlens-scorer:latest $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/fraudlens-scorer:latest
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/fraudlens-scorer:latest
cd ..

# Build and push dashboard
cd dashboard
docker build -t fraudlens-dashboard .
docker tag fraudlens-dashboard:latest $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/fraudlens-dashboard:latest
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/fraudlens-dashboard:latest
cd ..
```

---

### Step 6 — Deploy with Terraform

```bash
cd infrastructure

terraform init

terraform apply \
  -var="kafka_bootstrap_servers=YOUR_MSK_BOOTSTRAP_STRING_HERE"
```

Type `yes` when prompted.

Terraform will create:
- 2 DynamoDB tables (fraudlens-transactions, fraudlens-alerts)
- Elastic Beanstalk environment for Spring Boot
- Lambda + API Gateway for the Python scoring service
- IAM roles

At the end you'll see:
```
Outputs:
transaction_service_url = "fraudlens-tx-env.eba-xxxxx.us-east-1.elasticbeanstalk.com"
```

---

### Step 7 — Deploy the dashboard to S3 + CloudFront

This gives you the public recruiter URL.

```bash
# Build the React app pointing at your real API URL
cd dashboard
REACT_APP_API_URL=http://YOUR_ELASTIC_BEANSTALK_URL npm run build

# Create S3 bucket
aws s3 mb s3://fraudlens-dashboard-$(date +%s)
BUCKET=fraudlens-dashboard-XXXXX  # replace with the bucket name from above

# Upload build
aws s3 sync build/ s3://$BUCKET --delete

# Enable static website hosting
aws s3 website s3://$BUCKET --index-document index.html --error-document index.html

# Make public
aws s3api put-bucket-policy --bucket $BUCKET --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Effect\": \"Allow\",
    \"Principal\": \"*\",
    \"Action\": \"s3:GetObject\",
    \"Resource\": \"arn:aws:s3:::$BUCKET/*\"
  }]
}"
```

Your public URL will be:
```
http://BUCKET_NAME.s3-website-us-east-1.amazonaws.com
```

Send this to the recruiter.

---

### Step 8 — Tear it down when done (avoid charges)

```bash
# Delete S3 bucket contents
aws s3 rm s3://$BUCKET --recursive
aws s3 rb s3://$BUCKET

# Destroy Terraform resources
cd infrastructure
terraform destroy -var="kafka_bootstrap_servers=placeholder"

# Delete MSK cluster manually in AWS Console → MSK → Delete
```

---

## Cost estimate (AWS Free Tier)

| Service | Free tier | Notes |
|---|---|---|
| DynamoDB | 25 GB + 200M requests/month | Fully covered |
| Lambda | 1M requests/month | Fully covered |
| Elastic Beanstalk (t3.micro) | 750 hrs/month | Fully covered for 12 months |
| MSK (t3.small) | Not free tier | ~$0.21/hr — **delete after showing recruiter** |
| S3 | 5 GB + 20K requests | Fully covered |

**To keep costs near zero:** delete the MSK cluster when not actively demoing. The DynamoDB data persists so your alerts stay.

---

## Troubleshooting

**Docker build fails (Java OOM):**
```bash
# Increase Docker Desktop memory to 4GB
# Docker Desktop → Settings → Resources → Memory → 4 GB
```

**Kafka consumer not connecting:**
```bash
docker-compose logs fraud-scoring-service
# Should see "Kafka consumer started" — if not, wait 30s and restart:
docker-compose restart fraud-scoring-service
```

**Alerts not appearing after submitting:**
```bash
# Check scoring service processed the event
docker-compose logs fraud-scoring-service | grep "Scored transaction"
# Check Spring Boot received the score callback
docker-compose logs transaction-service | grep "FRAUD ALERT"
```

**terraform apply fails (permissions):**
Make sure your IAM user has `AdministratorAccess` — see Step 2.
