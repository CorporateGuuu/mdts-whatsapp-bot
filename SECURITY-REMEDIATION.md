# Credential exposure remediation

This change removes tracked environment files and private key material from the proposed current tree, clears example assignments, and extends the existing Nexus scanner across provider signatures. Scanner output contains paths, line numbers, and rule names only.

## Remaining provider work

All previously exposed credentials must be treated as compromised until provider verification. Removing files does not revoke credentials or remove Git history.

Create replacements, update every consuming deployment, deploy and smoke-test, revoke old credentials, then verify provider-side revocation. MDTSLive and nexustechhub share a generated credential family; update both consumers before revocation. Replace the exposed midastechnial private key wherever used. Public certificates are not private keys.

Production credentials must come from deployment secret stores. Environment files are ignored; tests requiring them must generate temporary synthetic fixtures. Review any build or deployment script that expected a deleted tracked file before merge.

## Verification

Run python3 Scripts/test_credential_check.py -v and python3 Scripts/check_supabase_credentials.py . in a full checkout. The scanner covers tracked current-tree files only and is a targeted gate, not proof of complete secret absence. Provider rotation, deployment validation, and historical scanning are separate requirements.
