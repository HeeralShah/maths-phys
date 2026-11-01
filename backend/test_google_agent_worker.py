import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.google_agent_worker import (
    AgentPlatformTransport,
    GoogleAgentRuntimeAdapter,
    GoogleAgentRuntimeSettings,
    RuntimeResult,
    build_native_pdf_chapter,
)


class FakeTransport:
    def __init__(self, events, elapsed_seconds=12.0):
        self.result = RuntimeResult(tuple(events), elapsed_seconds)
        self.calls = []

    def invoke(self, invocation, timeout_seconds):
        self.calls.append((invocation, timeout_seconds))
        return self.result


class GoogleAgentRuntimeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "chapter.pdf"
        # The registration boundary has already validated the real source PDF;
        # whole-document transport only needs to preserve the registered bytes.
        self.pdf_bytes = b"%PDF-1.7\nregistered native chapter bytes\n%%EOF"
        self.pdf.write_bytes(self.pdf_bytes)
        self.source_sha = hashlib.sha256(self.pdf_bytes).hexdigest()
        self.context = {
            "source": {
                "id": "source-1",
                "title": "Mechanics",
                "metadata": {
                    "local_file": {
                        "path": str(self.pdf),
                        "sha256": self.source_sha,
                        "page_count": 2,
                    }
                },
            },
            "learning_profile": {"known": ["calculus"]},
        }
        self.skills = self.root / "skills"
        (self.skills / "prepare-edition").mkdir(parents=True)
        (self.skills / "prepare-edition" / "SKILL.md").write_text(
            "# Prepare edition\nPreserve every source claim.", encoding="utf-8"
        )
        self.settings = GoogleAgentRuntimeSettings(
            project_id="study-project",
            location="europe-west2",
            runtime_resource_name=(
                "projects/study-project/locations/europe-west2/reasoningEngines/offline-agent"
            ),
            research_runtime_resource_name=(
                "projects/study-project/locations/europe-west2/reasoningEngines/research-agent"
            ),
            model="gemini-3.8-flash",
            max_llm_calls=6,
            max_total_tokens=100_000,
            job_budget_usd=1.0,
            total_budget_usd=20.0,
        )

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def complete_event(with_usage=True):
        event = {
            "content": {
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "package": {
                                    "complete": True,
                                    "edition": {"units": [{"id": "unit-1"}]},
                                }
                            }
                        )
                    }
                ]
            }
        }
        if with_usage:
            event["usage_metadata"] = {
                "prompt_token_count": 1_000,
                "candidates_token_count": 400,
                "thoughts_token_count": 100,
                "cached_content_token_count": 200,
                "total_token_count": 1_500,
            }
        return event

    def prepare_job(self, **payload):
        body = {"source_id": "source-1", "whole_document": True, **payload}
        return {
            "id": "job-1",
            "job_type": "prepare",
            "entity_id": "source-1",
            "payload": json.dumps(body),
        }

    def test_whole_chapter_is_sent_as_native_pdf_to_offline_runtime(self):
        transport = FakeTransport([self.complete_event()])
        adapter = GoogleAgentRuntimeAdapter(
            self.settings, transport=transport, skills_root=self.skills
        )

        artifact, cost = adapter.generate(
            self.prepare_job(), self.context, object(), ["prepare-edition"], 0.5
        )

        self.assertTrue(artifact["package"]["complete"])
        self.assertGreater(cost, 0)
        invocation, timeout = transport.calls[0]
        self.assertEqual(invocation.resource_name, self.settings.runtime_resource_name)
        self.assertEqual(timeout, self.settings.timeout_seconds)
        self.assertEqual(invocation.run_config, {"max_llm_calls": 6})
        self.assertEqual(
            invocation.message["parts"][0],
            {"inline_data": {"mime_type": "application/pdf", "data": self.pdf_bytes}},
        )
        envelope_text = invocation.message["parts"][1]["text"]
        envelope = json.loads(envelope_text)
        self.assertEqual(envelope["chapter"]["physical_pages"], [1, 2])
        self.assertEqual(envelope["chapter"]["source_sha256"], self.source_sha)
        self.assertNotIn(str(self.pdf), envelope_text)
        self.assertFalse(envelope["controls"]["research_enabled"])

    def test_research_requires_and_selects_separate_runtime(self):
        event = {
            "content": {
                "parts": [
                    {
                        "text": json.dumps(
                            {"plan": {"files": [], "signoff_id": "signoff-1"}}
                        )
                    }
                ]
            },
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 10},
        }
        transport = FakeTransport([event])
        adapter = GoogleAgentRuntimeAdapter(
            self.settings, transport=transport, skills_root=self.skills
        )
        job = {
            "id": "job-2",
            "job_type": "signoff",
            "entity_id": "section-1",
            "payload": json.dumps(
                {
                    "allow_web_research": True,
                    "research_domains": ["crossref.org"],
                }
            ),
        }

        artifact, _ = adapter.generate(job, {"included_units": []}, None, [], 0.5)

        self.assertIn("plan", artifact)
        invocation, _ = transport.calls[0]
        self.assertEqual(
            invocation.resource_name, self.settings.research_runtime_resource_name
        )
        self.assertEqual(len(invocation.message["parts"]), 1)
        envelope = json.loads(invocation.message["parts"][0]["text"])
        self.assertTrue(envelope["controls"]["research_enabled"])
        self.assertEqual(envelope["research"]["allowed_domains"], ["crossref.org"])

    def test_research_is_rejected_without_separate_runtime_before_transport(self):
        settings = GoogleAgentRuntimeSettings(
            project_id="study-project",
            location="europe-west2",
            runtime_resource_name=(
                "projects/study-project/locations/europe-west2/reasoningEngines/offline-agent"
            ),
            model="gemini-3.8-flash",
            max_llm_calls=4,
            max_total_tokens=50_000,
            job_budget_usd=1.0,
            total_budget_usd=20.0,
        )
        transport = FakeTransport([self.complete_event()])
        adapter = GoogleAgentRuntimeAdapter(
            settings, transport=transport, skills_root=self.skills
        )
        job = {
            "id": "job-3",
            "job_type": "signoff",
            "entity_id": "section-1",
            "payload": json.dumps({"allow_web_research": True}),
        }

        with self.assertRaisesRegex(ValueError, "separately configured research runtime"):
            adapter.generate(job, {}, None, [], 0.5)
        self.assertEqual(transport.calls, [])

    def test_changed_registered_pdf_is_rejected_before_transport(self):
        self.context["source"]["metadata"]["local_file"]["sha256"] = "0" * 64
        transport = FakeTransport([self.complete_event()])
        adapter = GoogleAgentRuntimeAdapter(
            self.settings, transport=transport, skills_root=self.skills
        )

        with self.assertRaisesRegex(ValueError, "changed since it was added"):
            adapter.generate(
                self.prepare_job(), self.context, None, ["prepare-edition"], 0.5
            )
        self.assertEqual(transport.calls, [])

    def test_absent_provider_usage_keeps_cost_unknown(self):
        transport = FakeTransport([self.complete_event(with_usage=False)])
        adapter = GoogleAgentRuntimeAdapter(
            self.settings, transport=transport, skills_root=self.skills
        )

        _, cost = adapter.generate(
            self.prepare_job(), self.context, None, ["prepare-edition"], 0.5
        )

        self.assertIsNone(cost)
        self.assertIsNone(adapter.last_usage.estimated_cost_usd)

    def test_whole_document_builder_preserves_bytes_without_rasterising(self):
        chapter = build_native_pdf_chapter(self.prepare_job(), self.context)
        self.assertEqual(chapter.data, self.pdf_bytes)
        self.assertEqual(chapter.physical_pages, (1, 2))
        self.assertEqual(chapter.original_page_count, 2)

    def test_environment_configuration_is_opt_in(self):
        with self.assertRaisesRegex(RuntimeError, "execution is disabled"):
            GoogleAgentRuntimeSettings.from_env({})

    def test_default_transport_does_not_create_client_until_invoked(self):
        calls = []
        AgentPlatformTransport(
            "study-project",
            "europe-west2",
            client_factory=lambda: calls.append("created"),
        )
        self.assertEqual(calls, [])

    def test_direct_argon_configuration_uses_argon_price_defaults(self):
        settings = GoogleAgentRuntimeSettings(
            project_id="study-project",
            location="europe-west2",
            runtime_resource_name=(
                "projects/study-project/locations/europe-west2/reasoningEngines/offline-agent"
            ),
            model="gemini-4-argon",
            max_llm_calls=4,
            max_total_tokens=50_000,
            job_budget_usd=1.0,
            total_budget_usd=20.0,
        )
        self.assertGreaterEqual(settings.input_usd_per_million, 2.20)
        self.assertGreaterEqual(settings.output_usd_per_million, 11.0)

    def test_stream_timeout_cannot_cross_agent_runtime_limit(self):
        with self.assertRaisesRegex(ValueError, "600-second limit"):
            GoogleAgentRuntimeSettings(
                project_id="study-project",
                location="europe-west2",
                runtime_resource_name=(
                    "projects/study-project/locations/europe-west2/reasoningEngines/offline-agent"
                ),
                model="gemini-3.8-flash",
                max_llm_calls=4,
                max_total_tokens=50_000,
                job_budget_usd=1.0,
                total_budget_usd=20.0,
                timeout_seconds=600,
            )


if __name__ == "__main__":
    unittest.main()
