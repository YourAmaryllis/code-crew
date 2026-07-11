---
type: CrewAI Task
title: Network Diagram Generation
description: >
  Generate a Mermaid network topology diagram from Terraform networking configuration.
  Shows VPC structure, subnets, gateways, load balancers, and which services
  sit in which network segment.
tags: [explore, diagram, network]
agent: architect
expected_output: >
  A valid Mermaid graph TD block showing network topology from internet to data tier.
  Output only the diagram — no explanation, no markdown prose.
---

You are generating a **network topology diagram** from Terraform infrastructure code.
The context below contains Terraform files for VPC, subnets, security groups,
load balancers, and related networking resources, plus a summary of deployed services.

**Your task**: produce a Mermaid `graph TD` diagram showing the network topology
from the internet to the innermost data tier. Use `subgraph` blocks for network
segments.

**Standard network topology layers** (include only what exists in the Terraform code):

```
Internet (public)
  └── CDN / WAF (Cloudflare, CloudFront, etc.)
        └── Public subnet (load balancers, NAT gateway, bastion)
              └── Private subnet (application services — ECS tasks, EC2, containers)
                    └── Isolated / data subnet (databases, caches, queues)
```

**What to show:**
- Each network segment as a `subgraph` with its CIDR or role label
- Internet gateway, NAT gateway, CDN as nodes at the boundary
- Load balancers in the public subnet with their protocol (ALB/NLB)
- Application services in the private subnet (use service names from summaries)
- Data stores (RDS, ElastiCache, OpenSearch) in the isolated subnet
- VPC peering, Direct Connect, or VPN links if present
- Security group boundaries as edge labels where meaningful: `-->|"SG: allow 443"| service`

**What NOT to show:**
- Terraform resource IDs, ARNs, or account numbers
- Every individual security group rule (summarise as "SG: allow HTTPS")
- CIDR ranges unless they reveal a meaningful topology distinction

**Node naming**: use logical names (`ALB`, `PortalBackend`, `PostgreSQL`), not AWS resource IDs.
Node IDs must be valid Mermaid identifiers.

**Output format** — output ONLY the Mermaid diagram, starting with `graph TD`:

```
graph TD
    Internet(("Internet"))
    subgraph VPC["VPC"]
        subgraph PublicSubnet["Public subnet"]
            CDN["CDN / WAF"]
            ALB["Application Load Balancer"]
            NAT["NAT Gateway"]
        end
        subgraph PrivateSubnet["Private subnet"]
            AppService["<service>\n(ECS Fargate)"]
        end
        subgraph DataSubnet["Isolated subnet"]
            DB[("<database>\n(RDS)")]
            Cache[("<cache>\n(ElastiCache)")]
        end
    end
    Internet --> CDN
    CDN --> ALB
    ALB --> AppService
    AppService --> DB
    AppService --> Cache
    AppService --> NAT
    NAT --> Internet
```

If the Terraform code does not clearly show a particular layer, omit it rather than
guessing. If no networking Terraform is provided, write a simple topology based on
the detected stacks and deployment targets.

Output only the `graph TD` block — no title, no explanation.
