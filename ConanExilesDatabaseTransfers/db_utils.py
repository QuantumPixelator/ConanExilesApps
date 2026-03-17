import os
import shutil
import sqlite3
import time
from typing import Dict, List, Tuple

LOG_PATH = os.path.join(os.path.dirname(__file__), 'transfer.log')

def _log(msg: str):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")

def copy_db(src: str, dst: str) -> None:
    shutil.copy2(src, dst)
    _log(f"Copied DB from {src} to {dst}")

def _connect(db_path: str):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _build_owner_variants(conn, owner_id):
    """Return list of owner identifiers to consider for a character: [id, playerId, guild]
    Preserves order and deduplicates. Uses an open connection."""
    ids = [owner_id]
    try:
        cur = conn.cursor()
        cur.execute("SELECT playerId, guild FROM characters WHERE id = ?", (owner_id,))
        r = cur.fetchone()
        if r:
            pid = r['playerId'] if 'playerId' in r.keys() else None
            guild = r['guild'] if 'guild' in r.keys() else None
            if pid is not None and pid not in ids:
                ids.append(pid)
            if guild is not None and guild not in ids:
                ids.append(guild)
    except Exception:
        pass
    return list(dict.fromkeys(ids))

def counts_for_owner(db_path: str, owner_id: int) -> Dict[str,int]:
    """Return counts for common ownership categories for the numeric owner_id."""
    q = {
        'items': "SELECT COUNT(*) AS c FROM item_inventory WHERE owner_id = ?",
        'item_properties': "SELECT COUNT(*) AS c FROM item_properties WHERE owner_id = ?",
        'buildings': "SELECT COUNT(*) AS c FROM buildings WHERE owner_id = ?",
        'destruction_history': "SELECT COUNT(*) AS c FROM destruction_history WHERE owner_id = ?",
        'game_events_owner': "SELECT COUNT(*) AS c FROM game_events WHERE ownerId = ?",
    }
    conn = _connect(db_path)
    cur = conn.cursor()
    out = {}
    try:
        for k, sql in q.items():
            # allow matching against character/playerId/guild variants
            owner_ids = _build_owner_variants(conn, owner_id)
            if len(owner_ids) == 1:
                cur.execute(sql, (owner_id,))
            else:
                ph = ','.join(['?'] * len(owner_ids))
                sql2 = sql.replace('= ?', f'IN ({ph})')
                cur.execute(sql2, tuple(owner_ids))
            out[k] = cur.fetchone()['c']
        # Dynamically count thralls/pets/followers in all relevant tables
        thrall_count = 0
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            cols = [c[1] for c in cur.fetchall()]
            for col in cols:
                if col.lower() in ('owner_id','character_id','char_id','player_id'):
                    try:
                        owner_ids = _build_owner_variants(conn, owner_id)
                        if len(owner_ids) == 1:
                            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (owner_id,))
                        else:
                            ph = ','.join(['?']*len(owner_ids))
                            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IN ({ph})", tuple(owner_ids))
                        thrall_count += cur.fetchone()[0]
                    except Exception:
                        continue
        out['thralls'] = thrall_count
    finally:
        conn.close()
    return out


def load_item_xref_file(xref_path: str) -> Dict[int,str]:
    """Parse the `item_xref` SQL file and return mapping template_id->name."""
    mapping = {}
    if not os.path.exists(xref_path):
        return mapping
    try:
        with open(xref_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # find patterns like: SELECT '10001' AS 'template_id', 'Stone' AS 'name', 'ingredient' AS 'type'
                if line.upper().startswith('SELECT') or line.upper().startswith('UNION ALL SELECT'):
                    # crude parsing: extract quoted tokens
                    parts = line.replace('UNION ALL ','').split('SELECT',1)[1]
                    # split by commas respecting quotes
                    tokens = []
                    cur = ''
                    inq = False
                    for ch in parts:
                        if ch == "'":
                            inq = not inq
                            cur += ch
                        elif ch == ',' and not inq:
                            tokens.append(cur.strip())
                            cur = ''
                        else:
                            cur += ch
                    if cur:
                        tokens.append(cur.strip())
                    if len(tokens) >= 2:
                        # first token contains template id
                        try:
                            tid = int(tokens[0].strip().strip("'"))
                            name = tokens[1].split('AS')[-1].strip().strip("' ")
                            # remove quotes
                            name = name.strip("'")
                            mapping[tid] = name
                        except Exception:
                            continue
    except Exception:
        return {}
    return mapping


def discover_owner_columns(db_path: str) -> List[Tuple[str,str]]:
    """Return list of (table, column) pairs where the column name looks ownership-related."""
    keywords = ['owner','owner_id','ownerid','player','playerid','guild','guildid']
    conn = _connect(db_path)
    cur = conn.cursor()
    out = []
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            cur.execute(f"PRAGMA table_info('{t}')")
            for col in cur.fetchall():
                name = col[1]
                lname = name.lower()
                if any(k in lname for k in keywords):
                    out.append((t, name))
    finally:
        conn.close()
    return out



def list_items_for_owner(db_path: str, owner_id: int, xref: Dict[int,str]=None, owner_is_guild: bool=False) -> List[Dict]:
    conn = _connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT item_id, owner_id, inv_type, template_id FROM item_inventory WHERE owner_id = ?", (owner_id,))
        rows = []
        for r in cur.fetchall():
            tid = r['template_id']
            name = xref.get(tid) if xref else None
            rows.append({'item_id': r['item_id'], 'template_id': tid, 'template_name': name, 'inv_type': r['inv_type']})
        return rows
    finally:
        conn.close()


def list_buildings_for_owner(db_path: str, owner_id: int, xref: Dict[int,str]=None, owner_is_guild: bool=False) -> List[Dict]:
    conn = _connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT b.object_id, b.owner_id, bp.template_id FROM buildings b LEFT JOIN buildable_health bp ON bp.object_id = b.object_id WHERE b.owner_id = ?", (owner_id,))
        out = []
        for r in cur.fetchall():
            obj = r['object_id']
            tid = r['template_id']
            # fetch actor class and coords
            cur.execute("SELECT class, x, y, z FROM actor_position WHERE id = ?", (obj,))
            ap = cur.fetchone()
            cls = ap['class'] if ap else None
            coords = (ap['x'], ap['y'], ap['z']) if ap else (None,None,None)
            name = xref.get(tid) if xref and tid is not None else None
            out.append({'object_id': obj, 'template_id': tid, 'template_name': name, 'class': cls, 'coords': coords})
        return out
    finally:
        conn.close()


def list_thralls_for_owner(db_path: str, owner_id: int, owner_is_guild: bool=False) -> List[Dict]:
    conn = _connect(db_path)
    cur = conn.cursor()
    try:
        out = []
        # Check if actors table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actors'")
        has_actors = cur.fetchone() is not None
        if has_actors:
            table = 'actors'
            owner_col = 'owner_id'
            # List all actors (placed followers) for this owner
            cur.execute(f"SELECT id, class, owner_id FROM {table} WHERE {owner_col} = ?", (owner_id,))
            for r in cur.fetchall():
                actor_id = r[0]
                cls = r[1] if len(r) > 1 else ''
                # Try to get coords/template_id/template_name if possible
                coords, template_id, template_name = (None, None, None), '', ''
                try:
                    cur.execute("SELECT x, y, z, template_id FROM actor_position WHERE id = ?", (actor_id,))
                    ap = cur.fetchone()
                    if ap:
                        coords = (ap[0], ap[1], ap[2])
                        template_id = str(ap[3]) if len(ap) > 3 and ap[3] is not None else ''
                except Exception:
                    pass
                if template_id:
                    try:
                        cur.execute("SELECT name FROM templates WHERE id = ?", (template_id,))
                        trow = cur.fetchone()
                        if trow and trow[0]:
                            template_name = str(trow[0])
                    except Exception:
                        pass
                if not template_name:
                    template_name = template_id if template_id else str(actor_id)
                out.append({
                    'follower_id': str(actor_id),
                    'class': cls,
                    'coords': str(coords),
                    'template_id': template_id,
                    'template_name': template_name,
                    'table': table,
                    'owner_col': owner_col
                })
            return out
        # fallback: follower_markers
        table = 'follower_markers'
        owner_col = 'owner_id'
        follower_col = 'follower_id'
        cur.execute(f"SELECT {follower_col} FROM {table} WHERE {owner_col} = ?", (owner_id,))
        for r in cur.fetchall():
            fid = r[follower_col] if isinstance(r, dict) and follower_col in r else r[0]
            # Try to get class/coords from actor_position
            cls, coords = '', (None, None, None)
            try:
                cur.execute("SELECT class, x, y, z FROM actor_position WHERE id = ?", (fid,))
                ap = cur.fetchone()
                if ap:
                    # ap: (class, x, y, z, ...)
                    cls = str(ap[0]) if ap[0] is not None else ''
                    coords = (ap[1], ap[2], ap[3]) if len(ap) >= 4 else (None, None, None)
            except Exception:
                pass
            template_id = ''
            template_name = str(fid)
            out.append({
                'follower_id': str(fid),
                'class': cls,
                'coords': str(coords),
                'template_id': template_id,
                'template_name': template_name,
                'table': table,
                'owner_col': owner_col
            })
        return out
    finally:
        conn.close()


def list_characters(db_path: str) -> List[Dict]:
    """Return list of characters as dicts: id, char_name, playerId, guild"""
    conn = _connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, char_name, playerId, guild FROM characters ORDER BY char_name COLLATE NOCASE")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def simulate_update_counts(db_path: str, source_id: int, categories: List[str], source_is_guild: bool=False) -> Dict[str,int]:
    # counts that would be affected
    conn = _connect(db_path)
    cur = conn.cursor()
    res = {}
    try:
        # build list of possible owner identifiers (id, playerId, guild)
        owner_ids = _build_owner_variants(conn, source_id)
        # helper to build IN clause params
        def in_clause_params(col):
            if not owner_ids:
                return (f"{col} = ?", (source_id,))
            placeholders = ','.join(['?'] * len(owner_ids))
            return (f"{col} IN ({placeholders})", tuple(owner_ids))
        if 'items' in categories or 'all' in categories:
            clause, params = in_clause_params('owner_id')
            cur.execute(f"SELECT COUNT(*) AS c FROM item_inventory WHERE {clause}", params)
            res['item_inventory'] = cur.fetchone()['c']
            cur.execute(f"SELECT COUNT(*) AS c FROM item_properties WHERE {clause}", params)
            res['item_properties'] = cur.fetchone()['c']
        if 'buildings' in categories or 'all' in categories:
            clause, params = in_clause_params('owner_id')
            cur.execute(f"SELECT COUNT(*) AS c FROM buildings WHERE {clause}", params)
            res['buildings'] = cur.fetchone()['c']
        if 'thralls' in categories or 'all' in categories:
            clause, params = in_clause_params('owner_id')
            try:
                cur.execute(f"SELECT COUNT(*) AS c FROM follower_markers WHERE {clause}", params)
                res['thralls'] = cur.fetchone()['c']
            except Exception:
                # fallback if follower_markers doesn't exist
                res['thralls'] = 0
        if 'game_events' in categories or 'all' in categories:
            # ownerId may match any of the owner identifiers
            clause, params = in_clause_params('ownerId')
            try:
                cur.execute(f"SELECT COUNT(*) AS c FROM game_events WHERE {clause}", params)
                res['game_events_owner'] = cur.fetchone()['c']
            except Exception:
                res['game_events_owner'] = 0
            # ownerGuildId refers to guild id only
            # guild-related game_events counts removed
    finally:
        conn.close()
    # provide legacy/alternate key names for callers
    res['items'] = res.get('item_inventory', 0)
    return res

def perform_transfer(db_path: str, source_id: int, target_id: int, categories: List[str], dry_run: bool=False, 
                     item_ids: List[int]=None, building_object_ids: List[int]=None, thrall_ids: List[int]=None,
                     set_source_guild_to_target: bool=False, target_is_guild: bool=False,
                     include_discovered_owner_columns: bool=True, source_is_guild: bool=False) -> Tuple[bool, Dict[str,int], str]:
    """
    Perform transfer from source_id to target_id for the requested categories.
    Returns (success, counts_changed, message)
    The function always operates on the provided db_path (which should be a copy already).
    """
    conn = _connect(db_path)
    cur = conn.cursor()
    before = simulate_update_counts(db_path, source_id, categories)
    changed = {}
    try:
        if dry_run:
            _log(f"Dry-run requested: source={source_id}, target={target_id}, cats={categories}")
            return True, before, 'Dry-run completed, no changes applied.'

        conn.execute('BEGIN')
        # Build owner identifier variants for source/target (id, playerId, guild)
        src_ids = _build_owner_variants(conn, source_id)
        tgt_ids = _build_owner_variants(conn, target_id)

        def q_in(col, ids):
            if not ids:
                return f"{col} = ?", (source_id,)
            ph = ','.join(['?']*len(ids))
            return f"{col} IN ({ph})", tuple(ids)

        # Only transfer selected assets (by id) from source to recipient
        # Items
        if 'items' in categories or 'all' in categories:
            if item_ids:
                placeholders = ','.join(['?']*len(item_ids))
                # update items where owner matches any of the source id variants
                clause, params = q_in('owner_id', src_ids)
                sql = f"UPDATE item_inventory SET owner_id = ? WHERE {clause} AND item_id IN ({placeholders})"
                exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params + tuple(item_ids)
                _log(f"Item transfer: SQL={sql}, params={exec_params}")
                cur.execute(sql, exec_params)
                changed['item_inventory'] = cur.rowcount
                sql2 = f"UPDATE item_properties SET owner_id = ? WHERE {clause} AND item_id IN ({placeholders})"
                _log(f"Item properties transfer: SQL={sql2}, params={exec_params}")
                cur.execute(sql2, exec_params)
                changed['item_properties'] = cur.rowcount
            else:
                clause, params = q_in('owner_id', src_ids)
                sql = f"UPDATE item_inventory SET owner_id = ? WHERE {clause}"
                exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params
                _log(f"Item transfer: SQL={sql}, params={exec_params}")
                cur.execute(sql, exec_params)
                changed['item_inventory'] = cur.rowcount
                sql2 = f"UPDATE item_properties SET owner_id = ? WHERE {clause}"
                _log(f"Item properties transfer: SQL={sql2}, params={exec_params}")
                cur.execute(sql2, exec_params)
                changed['item_properties'] = cur.rowcount

        # Buildings
        if 'buildings' in categories or 'all' in categories:
            clause, params_in = q_in('owner_id', src_ids)
            if building_object_ids:
                placeholders = ','.join(['?']*len(building_object_ids))
                sql = f"UPDATE buildings SET owner_id = ? WHERE {clause} AND object_id IN ({placeholders})"
                exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params_in + tuple(building_object_ids)
                _log(f"Building transfer: SQL={sql}, params={exec_params}")
                cur.execute(sql, exec_params)
                changed['buildings'] = cur.rowcount
            else:
                sql = f"UPDATE buildings SET owner_id = ? WHERE {clause}"
                exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params_in
                _log(f"Building transfer: SQL={sql}, params={exec_params}")
                cur.execute(sql, exec_params)
                changed['buildings'] = cur.rowcount

        # Thralls: update actors.owner_id for placed followers, or fallback to follower_markers if actors table is missing
        if 'thralls' in categories or 'all' in categories:
            # Check if actors table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actors'")
            has_actors = cur.fetchone() is not None
            if has_actors:
                if thrall_ids:
                    placeholders = ','.join(['?'] * len(thrall_ids))
                    clause, params_in = q_in('owner_id', src_ids)
                    sql = f"UPDATE actors SET owner_id = ? WHERE {clause} AND id IN ({placeholders})"
                    exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params_in + tuple(thrall_ids)
                    _log(f"Thrall transfer (actors): SQL={sql}, params={exec_params}")
                    cur.execute(sql, exec_params)
                    changed['thralls'] = cur.rowcount
                else:
                    clause, params_in = q_in('owner_id', src_ids)
                    sql = f"UPDATE actors SET owner_id = ? WHERE {clause}"
                    exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params_in
                    _log(f"Thrall transfer (actors): SQL={sql}, params={exec_params}")
                    cur.execute(sql, exec_params)
                    changed['thralls'] = cur.rowcount
            else:
                # Fallback: update follower_markers table
                # Detect follower_id conflicts (same follower already owned by target) and skip them
                skipped = []
                total_attempt = 0
                # build target owner_id set for subquery
                tgt_clause, tgt_params = q_in('owner_id', tgt_ids)
                # helper to fetch conflicting follower_ids
                try:
                    if thrall_ids:
                        # only consider the requested thrall_ids
                        placeholders = ','.join(['?'] * len(thrall_ids))
                        # which of these follower_ids already exist for the target owners?
                        q = f"SELECT follower_id FROM follower_markers WHERE {tgt_clause} AND follower_id IN ({placeholders})"
                        _log(f"Checking thrall conflicts: SQL={q}, params={tgt_params + tuple(thrall_ids)}")
                        cur.execute(q, tgt_params + tuple(thrall_ids))
                        skipped = [row[0] for row in cur.fetchall()]
                        # build list of to-move ids (exclude skipped)
                        move_ids = [int(x) for x in thrall_ids if int(x) not in skipped]
                        total_attempt = len(thrall_ids)
                    else:
                        # moving all thralls from source: find all follower_ids for source, then detect conflicts
                        clause, params_in = q_in('owner_id', src_ids)
                        q_src = f"SELECT follower_id FROM follower_markers WHERE {clause}"
                        _log(f"Listing source follower_ids: SQL={q_src}, params={params_in}")
                        cur.execute(q_src, params_in)
                        src_fids = [row[0] for row in cur.fetchall()]
                        total_attempt = len(src_fids)
                        if src_fids:
                            placeholders = ','.join(['?'] * len(src_fids))
                            q_conf = f"SELECT follower_id FROM follower_markers WHERE {tgt_clause} AND follower_id IN ({placeholders})"
                            _log(f"Checking thrall conflicts: SQL={q_conf}, params={tgt_params + tuple(src_fids)}")
                            cur.execute(q_conf, tgt_params + tuple(src_fids))
                            skipped = [row[0] for row in cur.fetchall()]
                        move_ids = [int(x) for x in src_fids if int(x) not in skipped]
                except Exception:
                    # If any error while checking, fallback to optimistic update with no skips
                    skipped = []
                    move_ids = thrall_ids if thrall_ids else None
                # perform update for non-conflicting follower_ids
                if move_ids:
                    placeholders = ','.join(['?'] * len(move_ids))
                    clause, params_in = q_in('owner_id', src_ids)
                    sql = f"UPDATE follower_markers SET owner_id = ? WHERE {clause} AND follower_id IN ({placeholders})"
                    exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params_in + tuple(move_ids)
                    _log(f"Thrall transfer (follower_markers): SQL={sql}, params={exec_params}")
                    cur.execute(sql, exec_params)
                    changed['thralls'] = cur.rowcount
                else:
                    # nothing moved
                    changed['thralls'] = 0
                if skipped:
                    changed['skipped_thralls'] = skipped
                changed['attempted_thralls'] = total_attempt

        # Game events (optional, not by id)
        if 'game_events' in categories or 'all' in categories:
            # ownerId may match any of the owner identifiers
            clause, params_in = q_in('ownerId', src_ids)
            sql = f"UPDATE game_events SET ownerId = ? WHERE {clause}"
            exec_params = (tgt_ids[0] if tgt_ids else target_id,) + params_in
            _log(f"Game events owner transfer: SQL={sql}, params={exec_params}")
            try:
                cur.execute(sql, exec_params)
                changed['game_events_owner'] = cur.rowcount
            except Exception:
                changed['game_events_owner'] = 0

        # character.guild updates removed (guild features disabled)

        conn.commit()
        _log(f"Performed transfer: source={source_id} -> target={target_id}, categories={categories}, changed={changed}")
        # integrity check
        cur.execute("PRAGMA integrity_check")
        ic = cur.fetchone()[0]
        if ic != 'ok':
            msg = f"Integrity check failed: {ic}"
            _log(msg)
            return False, changed, msg
        try:
            cur.execute('ANALYZE')
        except Exception:
            pass
        return True, changed, 'Transfer completed successfully.'
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        _log(f"Transfer failed: {e}")
        return False, {}, str(e)
    finally:
        conn.close()


def write_audit_csv(csv_path: str, record: Dict) -> None:
    """Append a transfer audit record (dict) to a CSV file. Creates header row if file doesn't exist."""
    import csv
    fieldnames = [
        'timestamp', 'db_path', 'pre_transfer_backup', 'source_id', 'target_id', 'categories',
        'item_ids', 'building_object_ids', 'thrall_ids', 'changed_json', 'message',
        'before_source', 'after_source', 'before_target', 'after_target'
    ]
    write_header = not os.path.exists(csv_path)
    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        # log record keys for debugging
        try:
            _log(f"write_audit_csv: record keys={list(record.keys())}, changed={record.get('changed')}, changed_json={record.get('changed_json')}")
        except Exception:
            pass
        row = {k: record.get(k, '') for k in fieldnames}
        # ensure JSON-serializable fields recorded as JSON strings
        import json as _json
        row['categories'] = _json.dumps(record.get('categories', []), ensure_ascii=False)
        row['item_ids'] = _json.dumps(record.get('item_ids', []), ensure_ascii=False)
        row['building_object_ids'] = _json.dumps(record.get('building_object_ids', []), ensure_ascii=False)
        row['thrall_ids'] = _json.dumps(record.get('thrall_ids', []), ensure_ascii=False)
        # accept either 'changed' or 'changed_json' in the incoming record
        changed_val = record.get('changed') if 'changed' in record else record.get('changed_json', {})
        row['changed_json'] = _json.dumps(changed_val or {}, ensure_ascii=False)
        # serialize before/after counts if present
        row['before_source'] = _json.dumps(record.get('before_source', {}), ensure_ascii=False)
        row['after_source'] = _json.dumps(record.get('after_source', {}), ensure_ascii=False)
        row['before_target'] = _json.dumps(record.get('before_target', {}), ensure_ascii=False)
        row['after_target'] = _json.dumps(record.get('after_target', {}), ensure_ascii=False)
        w.writerow(row)


def revert_transfer(transferred_db_path: str) -> Tuple[bool, str]:
    """Revert a transfer by restoring the pre-transfer backup alongside the transferred DB.
    Expects a pre-transfer backup file with suffix '.pre' (e.g., 'game_transferred_...db.pre').
    Returns (success, message).
    """
    pre_path = transferred_db_path + '.pre'
    if not os.path.exists(transferred_db_path):
        return False, f'Transferred DB not found: {transferred_db_path}'
    if not os.path.exists(pre_path):
        return False, f'Pre-transfer backup not found: {pre_path}'
    try:
        shutil.copy2(pre_path, transferred_db_path)
        _log(f'Reverted {transferred_db_path} from {pre_path}')
        return True, 'Revert successful.'
    except Exception as e:
        _log(f'Revert failed for {transferred_db_path}: {e}')
        return False, str(e)
