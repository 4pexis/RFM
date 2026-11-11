from __future__ import annotations

import pytest

from app.core.security import PermissionDenied, Role, ValidationError
from app.database.models import AccountStatus


def test_create_and_search(ctx):
    games = {g.slug: g for g in ctx.games.all()}
    ctx.accounts.create(username="Player_One", category="Mains", tags="Main, VIP",
                        game_ids=[games["blox_fruits"].id, games["fish"].id])
    ctx.accounts.create(username="alt_002", category="Alts", status=AccountStatus.PAUSED,
                        game_ids=[games["fish"].id])

    assert ctx.accounts.count() == 2
    assert [a.username for a in ctx.accounts.search("player")] == ["Player_One"]
    assert [a.username for a in ctx.accounts.search("vip")] == ["Player_One"]  # busca em tags
    assert len(ctx.accounts.search(game_id=games["fish"].id)) == 2
    assert [a.username for a in ctx.accounts.search(game_id=games["blox_fruits"].id)] == ["Player_One"]
    assert [a.username for a in ctx.accounts.search(status=AccountStatus.PAUSED)] == ["alt_002"]
    assert [a.username for a in ctx.accounts.search(category="Alts")] == ["alt_002"]
    assert ctx.accounts.categories() == ["Alts", "Mains"]
    account = ctx.accounts.search("player")[0]
    assert account.tags == "main,vip"
    assert account.game_names == "Blox Fruits, Fisch"  # utilizável fora da sessão do banco


def test_validation(ctx):
    ctx.accounts.create(username="duplicado")
    for bad in ("ab", "nome com espaço", "x" * 21, ""):
        with pytest.raises(ValidationError):
            ctx.accounts.create(username=bad)
    with pytest.raises(ValidationError):
        ctx.accounts.create(username="DUPLICADO")  # único sem diferenciar maiúsculas
    with pytest.raises(ValidationError):
        ctx.accounts.create(username="valido_1", roblox_user_id="abc")
    with pytest.raises(ValidationError):
        ctx.accounts.create(username="valido_2", level=-1)
    with pytest.raises(ValidationError):
        ctx.accounts.create(username="valido_3", status="inexistente")
    assert ctx.accounts.count() == 1


def test_credentials_are_refused(ctx):
    cookie = "_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in|_ABC"
    with pytest.raises(ValidationError):
        ctx.accounts.create(username="conta_x", notes=cookie)
    assert ctx.accounts.count() == 0


def test_like_wildcards_are_escaped(ctx):
    ctx.accounts.create(username="abc_def")
    ctx.accounts.create(username="abcXdef")
    assert [a.username for a in ctx.accounts.search("c_d")] == ["abc_def"]
    assert ctx.accounts.search("%") == []
    assert ctx.accounts.search("' OR 1=1 --") == []


def test_update_delete_and_history(ctx):
    game = ctx.games.all()[0]
    account = ctx.accounts.create(username="historico", game_ids=[game.id])
    updated = ctx.accounts.update(account.id, status=AccountStatus.DONE, level=50, game_ids=[])
    assert (updated.status, updated.level, updated.games) == (AccountStatus.DONE, 50, [])
    actions = [log.action for log in ctx.accounts.history(account.id)]
    assert set(actions) == {"account.create", "account.update"}
    ctx.accounts.delete(account.id)
    assert ctx.accounts.get(account.id) is None


def test_csv_roundtrip(ctx, tmp_path):
    source = tmp_path / "in.csv"
    source.write_text(
        "usuario;categoria;nivel;status;tags;jogos\n"
        "conta_01;Farm;120;Ativa;a,b;Blox Fruits|Fisch\n"
        "conta_02;Farm;;paused;;\n"
        "x;Farm;1;;;\n"                      # usuário inválido
        "conta_03;Farm;1;;;Jogo Inexistente\n",  # jogo desconhecido
        encoding="utf-8",
    )
    result = ctx.accounts.import_csv(source)
    assert (result.created, result.updated, len(result.errors)) == (2, 0, 2)
    assert "Linha 4" in result.errors[0] and "Linha 5" in result.errors[1]
    first = ctx.accounts.search("conta_01")[0]
    assert (first.level, first.status, first.game_names) == (120, "active", "Blox Fruits, Fisch")

    exported = tmp_path / "out.csv"
    assert ctx.accounts.export_csv(exported) == 2
    again = ctx.accounts.import_csv(exported)  # reimportar atualiza, não duplica
    assert (again.created, again.updated, again.errors) == (0, 2, [])
    assert ctx.accounts.count() == 2


def test_scales_to_hundreds(ctx):
    for i in range(600):
        ctx.accounts.create(username=f"farm_{i:04d}", category=f"Lote {i % 6}")
    assert ctx.accounts.count() == 600
    assert len(ctx.accounts.search("farm_05")) == 100
    assert len(ctx.accounts.search(category="Lote 3")) == 100


def test_permissions(ctx):
    account = ctx.accounts.create(username="protegida")
    ctx.config.change_role(Role.VIEWER)
    with pytest.raises(PermissionDenied):
        ctx.accounts.create(username="bloqueada")
    with pytest.raises(PermissionDenied):
        ctx.accounts.update(account.id, level=2)
    ctx.config.change_role(Role.OPERATOR)
    ctx.accounts.update(account.id, level=2)
    with pytest.raises(PermissionDenied):
        ctx.accounts.delete(account.id)
    with pytest.raises(PermissionDenied):
        ctx.config.set_many({"backup.keep": 3})
    ctx.config.change_role(Role.ADMIN)
    ctx.accounts.delete(account.id)
