import os
import pytest
from apps.api.aiopt_web.secrets_store import EnvironmentSecretStore,WindowsDpapiSecretStore
def test_environment_secrets_are_retrieved_and_masked_without_mutation(monkeypatch):
    store=EnvironmentSecretStore();monkeypatch.setenv("TEST_PROVIDER_KEY","sensitive-value");assert store.exists("TEST_PROVIDER_KEY");assert store.get("TEST_PROVIDER_KEY")=="sensitive-value";assert store.mask("TEST_PROVIDER_KEY")=="TE***"
    with pytest.raises(RuntimeError):store.save("TEST_PROVIDER_KEY","replacement")
@pytest.mark.skipif(os.name!="nt",reason="Windows DPAPI test")
def test_dpapi_save_retrieve_rotate_delete_and_ciphertext(tmp_path):
    store=WindowsDpapiSecretStore(tmp_path);store.save("provider-key","first-secret");path=next(tmp_path.iterdir());assert b"first-secret" not in path.read_bytes();assert store.get("provider-key")=="first-secret";assert store.mask("provider-key")=="pr***";store.rotate("provider-key","second-secret");assert store.get("provider-key")=="second-secret";store.delete("provider-key");assert not store.exists("provider-key")
