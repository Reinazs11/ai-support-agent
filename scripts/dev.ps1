param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "help",
        "infra",
        "migrate",
        "api",
        "start",
        "check",
        "auth",
        "auth-live",
        "smoke",
        "seed-eval",
        "eval"
    )]
    [string]$Command = "help",

    [string]$BaseUrl = "http://localhost:8000",
    [double]$SmokeMaxCostUsd = 0.005,
    [double]$EvalMaxCostUsd = 0.05,
    [string]$EvalManifestPath = "reports/evals/eval-corpus-manifest.json"
)

$ErrorActionPreference = "Stop"
$InvariantCulture = [System.Globalization.CultureInfo]::InvariantCulture
$Python = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $Python = ".\.venv\Scripts\python.exe"
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "> $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Show-Help {
    Write-Host "Usage: .\scripts\dev.ps1 <command>"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  infra      Start local Postgres and Qdrant with Docker Compose"
    Write-Host "  migrate    Run Alembic migrations"
    Write-Host "  api        Run the FastAPI app with reload"
    Write-Host "  start      Run infra, migrate, then api"
    Write-Host "  check      Run compileall, pytest, and ruff"
    Write-Host "  auth       Check OpenAI configuration without an API call"
    Write-Host "  auth-live  Verify OpenAI API access without prompts or documents"
    Write-Host "  smoke      Run the low-cost live RAG smoke test"
    Write-Host "  seed-eval  Upload and ingest the eval corpus"
    Write-Host "  eval       Run deterministic RAG evaluation"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\scripts\dev.ps1 start"
    Write-Host "  .\scripts\dev.ps1 check"
    Write-Host "  .\scripts\dev.ps1 seed-eval"
    Write-Host "  .\scripts\dev.ps1 eval"
}

switch ($Command) {
    "help" {
        Show-Help
    }
    "infra" {
        Invoke-External "docker" @("compose", "up", "-d", "postgres", "qdrant")
    }
    "migrate" {
        Invoke-External $Python @("-m", "alembic", "upgrade", "head")
    }
    "api" {
        Invoke-External $Python @("-m", "uvicorn", "app.main:app", "--reload")
    }
    "start" {
        Invoke-External "docker" @("compose", "up", "-d", "postgres", "qdrant")
        Invoke-External $Python @("-m", "alembic", "upgrade", "head")
        Invoke-External $Python @("-m", "uvicorn", "app.main:app", "--reload")
    }
    "check" {
        Invoke-External $Python @("-m", "compileall", "app", "scripts", "tests")
        Invoke-External $Python @("-m", "pytest")
        Invoke-External $Python @("-m", "ruff", "check", ".")
    }
    "auth" {
        Invoke-External $Python @("-m", "scripts.check_openai_auth")
    }
    "auth-live" {
        Invoke-External $Python @("-m", "scripts.check_openai_auth", "--live")
    }
    "smoke" {
        Invoke-External $Python @(
            "-m",
            "scripts.smoke_live_rag",
            "--base-url",
            $BaseUrl,
            "--max-cost-usd",
            $SmokeMaxCostUsd.ToString("G", $InvariantCulture)
        )
    }
    "seed-eval" {
        Invoke-External $Python @(
            "-m",
            "scripts.seed_eval_corpus",
            "--base-url",
            $BaseUrl,
            "--manifest-path",
            $EvalManifestPath
        )
    }
    "eval" {
        Invoke-External $Python @(
            "-m",
            "scripts.run_eval",
            "--base-url",
            $BaseUrl,
            "--document-manifest-path",
            $EvalManifestPath,
            "--max-total-cost-usd",
            $EvalMaxCostUsd.ToString("G", $InvariantCulture)
        )
    }
}
