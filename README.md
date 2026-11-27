# chapters

Infrastructure code for a self-hosted Open WebUI deployment, plus a
custom tool and skill for deterministic supplier-invoice totals.

## Contents

- `main.tf` — Terraform config provisioning an AWS EC2 instance (with
  Elastic IP, security group, and a Caddy-fronted TLS setup via nip.io)
  that runs Open WebUI via Docker Compose.
- `docker-compose.yml` — the Open WebUI service definition deployed to
  that instance.
- `tools/invoice_total_calculator.py` — an Open WebUI tool that sums the
  "Gesamtbetrag" (grand total) of supplier invoices/credit notes from a
  knowledge base, instead of relying on the model's own arithmetic.
- `skills/supplier-invoice-total/SKILL.md` — the skill that tells the
  model when and how to call that tool.

## Usage

```
terraform init
terraform apply
```

Requires AWS credentials in the environment and a `chapters` EC2 key
pair already present in the target AWS account/region.
