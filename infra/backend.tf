terraform {
  # Local-only profile. The state contains no secret values and is ignored by Git.
  backend "local" {
    path = "state/local.tfstate"
  }
}
