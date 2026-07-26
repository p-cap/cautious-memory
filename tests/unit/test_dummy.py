# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import sys
from types import ModuleType, SimpleNamespace
def test_vertex_agent_label_identifies_the_model() -> None:
    from app.agent import agent_label

    assert agent_label().startswith("vertex-ai:")


def test_vertex_agent_uses_adc_configuration(monkeypatch) -> None:
    from app import agent

    calls: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            calls["client"] = kwargs
            self.models = self

        def generate_content(self, **kwargs):
            calls["request"] = kwargs
            return SimpleNamespace(text="proposal")

    class FakeHttpOptions:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    types_module = ModuleType("google.genai.types")
    genai_module.Client = FakeClient
    types_module.HttpOptions = FakeHttpOptions
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)
    monkeypatch.setattr(agent, "GOOGLE_CLOUD_PROJECT", "p-cap-476219")
    monkeypatch.setattr(agent, "GOOGLE_CLOUD_LOCATION", "global")
    monkeypatch.setattr(agent, "GEMINI_MODEL", "gemini-2.5-flash")

    assert agent._create_response("prepare a local draft") == "proposal"
    assert calls["client"] == {
        "vertexai": True,
        "project": "p-cap-476219",
        "location": "global",
        "http_options": calls["client"]["http_options"],
    }
    assert calls["client"]["http_options"].kwargs == {"api_version": "v1"}
    assert calls["request"] == {
        "model": "gemini-2.5-flash",
        "contents": "prepare a local draft",
    }
