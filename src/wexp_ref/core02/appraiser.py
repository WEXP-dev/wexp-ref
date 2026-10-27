"""WEXP Core logical implementation for Core-02 normalized-input reference candidate; bounded qualification only.

This module implements the Core over already normalized logical values. Its JSON
friendly representation is a local harness, not a WEXP wire format. It does not
authenticate findings, profiles, registries or the events those findings describe.

appraise(input, profiles=None) -> all twenty logical Appraisal components.
Opaque atoms compare as already normalized Unicode scalar strings. Profile scoped
atoms are [immutable_profile_id, local_value]. Sets are lists, maps of capabilities
are lists of {capability: initial_name | [profile_id, local_name], status: ...}.
The configured profiles catalog binds exact immutable identities to vocabularies:
{id: {tokens: {name: {category: ..., current_scope_capability?: ...}},
      relation_tokens: [...], scope_names: [...]}}.
Catalog identity and normalization are caller premises; no signature is inferred.
"""
from copy import deepcopy
from itertools import combinations
import json

SEMANTICS = 'wexp-core-2'
CANDIDATE = 'Core-02 normalized-input reference candidate; bounded qualification only'
BASES = ('observation', 'intent', 'invocation', 'execution')
QUALIFIERS = ('PROV', 'IV')
STATUSES = ('supported', 'unsupported', 'not-evaluated')
GROUNDINGS = ('asserted-only', 'attributed', 'attested', 'not-evaluated')
COUNTER_STATUSES = ('not-supplied', 'not-evaluated', 'resolved-no-defeat',
                    'unresolved-material', 'defeating')
CAPABILITIES = (
    'carrier-mapping', 'authenticity', 'target-binding', 'boundary-grounding',
    'observation-support', 'intent-support', 'invocation-support',
    'execution-support', 'provenance-support', 'independent-verification',
    'composition', 'counter-evidence',
)
DERIVED_FATAL = ('E_MALFORMED_NORMALIZED_INPUT', 'E_UNSUPPORTED_SEMANTICS_VERSION',
                 'E_PROFILE_MAPPING_INVALID', 'E_CLAIM_OUT_OF_DOMAIN')
SUPPLIED_FATAL = ('E_UNKNOWN_CRITICAL_SEMANTIC', 'E_INTEGRITY_INVALID',
                  'E_BINDING_MISMATCH', 'E_CHAIN_DESCRIPTION_INVALID')
SUBSTANTIVE = (
    'E_CHAIN_UNBOUND', 'E_SHARED_VERIFICATION_ROOT', 'E_BASE_EXCEEDS_BOUNDARY',
    'E_BOUNDARY_NOT_SUPPORTED', 'E_EXACT_CLAIM_NOT_SUPPORTED',
    'E_MISSING_REQUIRED_EVIDENCE', 'E_EVIDENCE_NOT_BOUND',
    'E_EVIDENCE_COVERAGE_MISMATCH', 'E_PROV_NOT_SUPPORTED', 'E_IV_NOT_SUPPORTED',
    'E_COUNTER_EVIDENCE_UNRESOLVED', 'E_COUNTER_EVIDENCE_DEFEATING',
    'E_COMPOSITION_WARRANT_MISSING', 'E_INDEPENDENCE_NOT_ESTABLISHED',
)
GAPS = ('E_BASE_NOT_EVALUATED', 'E_BOUNDARY_NOT_EVALUATED', 'E_PROV_NOT_EVALUATED',
        'E_IV_NOT_EVALUATED', 'E_COMPOSITION_NOT_EVALUATED',
        'E_COUNTER_EVIDENCE_NOT_EVALUATED')
CORE_REGISTRY = {**{t: {'category': 'fatal'} for t in DERIVED_FATAL + SUPPLIED_FATAL},
                 **{t: {'category': 'substantive'} for t in SUBSTANTIVE},
                 **{t: {'category': 'evaluation-gap'} for t in GAPS}}
CORE_REGISTRY['E_COMPOSITION_NOT_EVALUATED']['current_scope_capability'] = 'composition'


class Malformed(ValueError):
    """Stage 3: a malformed logical input in the local representation."""


class MappingInvalid(ValueError):
    """Stage 4: recognized types violate a normalized cross-field invariant."""


def _key(value):
    # Named set fields compare mathematically even before canonical serialization.
    # Profile atom pairs and capability pairs retain their ordered-pair identity.
    set_fields = {'qualifiers', 'basis_refs', 'reasons', 'limitations',
                  'affected_claims', 'profile_identifiers'}
    def normalize(v):
        if type(v) is dict:
            result = {k: normalize(x) for k, x in v.items()}
            for k in set_fields & result.keys():
                if type(result[k]) is list:
                    result[k] = sorted(result[k], key=lambda x: json.dumps(
                        x, ensure_ascii=True, sort_keys=True, separators=(',', ':')))
            return result
        if type(v) is list:
            return [normalize(x) for x in v]
        return v
    return json.dumps(normalize(value), ensure_ascii=True, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def _set(values):
    """Deterministic serialization of a mathematical union, after type checking."""
    return [deepcopy(v) for _, v in sorted({_key(v): v for v in values}.items())]


def _record(value, required, optional=()):
    required, optional = set(required), set(optional)
    if type(value) is not dict or not required <= set(value) or set(value) - required - optional:
        raise Malformed('record members')


def _text(value, nonempty=False):
    if type(value) is not str or (nonempty and not value) or any(
            0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise Malformed('Unicode scalar text atom')


def _enum(value, choices):
    _text(value)
    if value not in choices:
        raise Malformed('closed enumeration')


def _list(value):
    if type(value) is not list:
        raise Malformed('logical set representation')


def _members(value, validate, unique=True):
    _list(value)
    for item in value:
        validate(item)
    if unique and len({_key(v) for v in value}) != len(value):
        raise Malformed('repeated mathematical set member')


def _atom(value):
    if type(value) is not list or len(value) != 2:
        raise Malformed('profile-scoped atom pair')
    _text(value[0], nonempty=True)
    _text(value[1])


def _claim(value):
    _record(value, ('base', 'qualifiers'))
    _enum(value['base'], BASES)
    _members(value['qualifiers'], lambda q: _enum(q, QUALIFIERS))


def _admissible(value):
    return 'PROV' not in value['qualifiers'] or value['base'] == 'execution'


def _claim_key(value):
    return value['base'], frozenset(value['qualifiers'])


def _affected(value):
    if value == 'all-admissible-claims':
        return
    _members(value, _claim)


def _common_finding(value):
    _text(value['target'])
    _text(value['evaluation_context_ref'])
    _enum(value['target_binding'], STATUSES)
    _members(value['basis_refs'], _atom)
    _members(value['reasons'], lambda t: _text(t, nonempty=True))
    _members(value['limitations'], _atom)


def _shape(input):
    """Validate every stage-3 condition before attempting a stage-4 check."""
    _record(input, ('semantics_version', 'target', 'asserted_claim', 'evaluation_context',
                    'boundary_finding', 'base_findings', 'qualifier_findings',
                    'recorder_relations', 'counter_evidence', 'evaluation_scope',
                    'profile_evaluation_gaps', 'inherited_limitations', 'fatal_conditions'))
    _text(input['target'])
    _claim(input['asserted_claim'])
    context = input['evaluation_context']
    _record(context, ('id', 'evaluated_at', 'trust_configuration', 'profile_identifiers'))
    for field in ('id', 'evaluated_at', 'trust_configuration'):
        _text(context[field])
    _members(context['profile_identifiers'], lambda x: _text(x, nonempty=True))
    boundary = input['boundary_finding']
    common = ('target', 'evaluation_context_ref', 'target_binding', 'basis_refs',
              'reasons', 'limitations')
    _record(boundary, common + ('status', 'grounding'), ('ceiling_base',))
    _common_finding(boundary)
    _enum(boundary['status'], STATUSES)
    _enum(boundary['grounding'], GROUNDINGS)
    if 'ceiling_base' in boundary:
        _enum(boundary['ceiling_base'], BASES)

    def base(f):
        _record(f, common + ('base', 'semantic_validation'))
        _common_finding(f)
        _enum(f['base'], BASES)
        _enum(f['semantic_validation'], STATUSES)

    def qualifier(f):
        _record(f, common + ('qualifier', 'qualified_base', 'semantic_validation',
                             'independence_validation'))
        _common_finding(f)
        _enum(f['qualifier'], QUALIFIERS)
        _enum(f['qualified_base'], BASES)
        _enum(f['semantic_validation'], STATUSES)
        _enum(f['independence_validation'], STATUSES + ('not-applicable',))

    # Duplicate aggregates, including byte-identical duplicates, are stage 4.
    _members(input['base_findings'], base, unique=False)
    _members(input['qualifier_findings'], qualifier, unique=False)

    def relation(r):
        _record(r, ('profile_identifier', 'relation_token', 'subject_ref', 'object_ref',
                    'basis_refs', 'limitations'))
        _text(r['profile_identifier'], nonempty=True)
        _text(r['relation_token'], nonempty=True)
        _atom(r['subject_ref'])
        _atom(r['object_ref'])
        _members(r['basis_refs'], _atom)
        _members(r['limitations'], _atom)

    def counter(c):
        _record(c, ('status', 'affected_claims', 'basis_refs', 'reasons', 'limitations'))
        _enum(c['status'], COUNTER_STATUSES)
        _affected(c['affected_claims'])
        _members(c['basis_refs'], _atom)
        _members(c['reasons'], lambda t: _text(t, nonempty=True))
        _members(c['limitations'], _atom)

    def scope(s):
        _record(s, ('capability', 'status'))
        _enum(s['status'], ('evaluated', 'not-evaluated'))
        cap = s['capability']
        if type(cap) is str:
            _enum(cap, CAPABILITIES)
        elif type(cap) is list:
            if len(cap) != 2:
                raise Malformed('scope extension must be an ordered pair')
            for part in cap:
                _text(part, nonempty=True)
        else:
            raise Malformed('capability name or extension pair')

    def gap(g):
        _record(g, ('target', 'evaluation_context_ref', 'token', 'affected_claims',
                    'basis_refs', 'limitations'), ('current_scope_capability',))
        _text(g['target'])
        _text(g['evaluation_context_ref'])
        _text(g['token'], nonempty=True)
        _affected(g['affected_claims'])
        _members(g['basis_refs'], _atom)
        _members(g['limitations'], _atom)
        if 'current_scope_capability' in g:
            _enum(g['current_scope_capability'], CAPABILITIES)

    _members(input['recorder_relations'], relation)
    _members(input['counter_evidence'], counter)
    _members(input['evaluation_scope'], scope, unique=False)
    _members(input['profile_evaluation_gaps'], gap)
    _members(input['inherited_limitations'], _atom)
    _members(input['fatal_conditions'], lambda t: _text(t, nonempty=True))


def _cross(input, profiles):
    """Cross-field identity/category/status checks, without adding evidence."""
    applied = input['evaluation_context']['profile_identifiers']
    for pid in applied:
        if pid not in profiles:
            raise MappingInvalid('unresolved immutable profile identity')
    # Catalog configuration is a caller premise. Its syntax is checked explicitly
    # rather than accidentally allowing arbitrary dict shapes as valid bindings.
    def catalog_name(value):
        return type(value) is str and bool(value) and all(
            not 0xD800 <= ord(c) <= 0xDFFF for c in value)

    for pid in applied:
        p = profiles[pid]
        if type(p) is not dict or set(p) != {'tokens', 'relation_tokens', 'scope_names'}:
            raise MappingInvalid('invalid profile catalog record')
        if type(p['tokens']) is not dict or type(p['relation_tokens']) is not list or type(p['scope_names']) is not list:
            raise MappingInvalid('invalid profile catalog vocabulary')
        for names in (p['relation_tokens'], p['scope_names']):
            if any(not catalog_name(n) for n in names) or len(set(names)) != len(names):
                raise MappingInvalid('invalid profile vocabulary names')
        for name, registration in p['tokens'].items():
            if not catalog_name(name) or type(registration) is not dict:
                raise MappingInvalid('invalid profile token registration')
            if set(registration) not in ({'category'}, {'category', 'current_scope_capability'}):
                raise MappingInvalid('invalid profile token registration fields')
            if registration['category'] not in ('fatal', 'substantive', 'evaluation-gap'):
                raise MappingInvalid('invalid profile token category')
            if 'current_scope_capability' in registration and (
                registration['category'] != 'evaluation-gap' or
                registration['current_scope_capability'] not in ('authenticity', 'composition')
            ):
                raise MappingInvalid('invalid profile token capability')

    def registration(token, category):
        if token in CORE_REGISTRY:
            result = CORE_REGISTRY[token]
        else:
            matches = [profiles[p]['tokens'][token] for p in applied if token in profiles[p]['tokens']]
            if len(matches) != 1:
                raise MappingInvalid('absent or ambiguous non-Core token')
            result = matches[0]
        if result['category'] != category:
            raise MappingInvalid('wrong token category')
        return result

    def atoms(values):
        if any(a[0] not in applied for a in values):
            raise MappingInvalid('unbound profile-scoped atom')

    def scoped(f):
        if f['target'] != input['target'] or f['evaluation_context_ref'] != input['evaluation_context']['id']:
            raise MappingInvalid('foreign target or context')

    findings = [input['boundary_finding']] + input['base_findings'] + input['qualifier_findings']
    for f in findings:
        scoped(f)
        atoms(f['basis_refs'])
        atoms(f['limitations'])
        for token in f['reasons']:
            registration(token, 'substantive')
    atoms(input['inherited_limitations'])
    if len({f['base'] for f in input['base_findings']}) != len(input['base_findings']):
        raise MappingInvalid('duplicate base aggregate key')
    if len({(f['qualifier'], f['qualified_base']) for f in input['qualifier_findings']}) != len(input['qualifier_findings']):
        raise MappingInvalid('duplicate qualifier aggregate key')
    boundary = input['boundary_finding']
    if boundary['status'] == 'supported' and 'ceiling_base' not in boundary:
        raise MappingInvalid('supported boundary without ceiling')
    if (boundary['status'] == 'not-evaluated') != (boundary['grounding'] == 'not-evaluated'):
        raise MappingInvalid('incompatible boundary status and grounding')
    for f in input['qualifier_findings']:
        if f['qualifier'] == 'PROV':
            if f['qualified_base'] != 'execution' or f['independence_validation'] != 'not-applicable':
                raise MappingInvalid('invalid PROV combination')
        elif f['independence_validation'] == 'not-applicable':
            raise MappingInvalid('invalid IV combination')
    for r in input['recorder_relations']:
        pid = r['profile_identifier']
        if pid not in applied or r['relation_token'] not in profiles[pid]['relation_tokens']:
            raise MappingInvalid('unbound recorder relation vocabulary')
        atoms([r['subject_ref'], r['object_ref']] + r['basis_refs'] + r['limitations'])

    def affected(value):
        if value != 'all-admissible-claims' and (not value or any(not _admissible(c) for c in value)):
            raise MappingInvalid('empty or inadmissible affected claim set')

    counters = input['counter_evidence']
    if not counters:
        raise MappingInvalid('counter sentinel absent')
    for c in counters:
        if c['status'] == 'not-supplied':
            if len(counters) != 1 or any(c[k] for k in ('affected_claims', 'basis_refs', 'reasons', 'limitations')):
                raise MappingInvalid('invalid counter sentinel')
        else:
            affected(c['affected_claims'])
        atoms(c['basis_refs'])
        atoms(c['limitations'])
        for token in c['reasons']:
            registration(token, 'substantive')
    for g in input['profile_evaluation_gaps']:
        scoped(g)
        affected(g['affected_claims'])
        atoms(g['basis_refs'])
        atoms(g['limitations'])
        reg = registration(g['token'], 'evaluation-gap')
        if 'current_scope_capability' in g:
            if g['current_scope_capability'] not in ('authenticity', 'composition'):
                raise MappingInvalid('recognized but disallowed current-scope marker')
            if reg.get('current_scope_capability') != g['current_scope_capability']:
                raise MappingInvalid('marker/token capability mismatch')
    for t in input['fatal_conditions']:
        registration(t, 'fatal')
        if t in DERIVED_FATAL:
            raise MappingInvalid('appraiser-derived fatal supplied as input')

    scope = {}
    for entry in input['evaluation_scope']:
        cap = entry['capability']
        if type(cap) is list:
            pid, name = cap
            if pid not in applied or name not in profiles[pid]['scope_names']:
                raise MappingInvalid('unbound extension scope key')
        key = _key(cap)
        if key in scope:
            raise MappingInvalid('duplicate scope key')
        scope[key] = entry['status']
    if any(_key(c) not in scope for c in CAPABILITIES):
        raise MappingInvalid('missing initial capability')
    scope = {c: scope[_key(c)] for c in CAPABILITIES}
    if scope['carrier-mapping'] != 'evaluated':
        raise MappingInvalid('complete input must have evaluated carrier mapping')
    governed = {'target-binding': [f['target_binding'] for f in findings],
                'boundary-grounding': [boundary[f] for f in ('status', 'target_binding', 'grounding')],
                'counter-evidence': [c['status'] for c in counters]}
    for b in BASES:
        governed[b + '-support'] = [f[k] for f in input['base_findings'] if f['base'] == b
                                    for k in ('target_binding', 'semantic_validation')]
    for qualifier, capability in (('PROV', 'provenance-support'), ('IV', 'independent-verification')):
        fields = ('target_binding', 'semantic_validation') + (('independence_validation',) if qualifier == 'IV' else ())
        governed[capability] = [f[k] for f in input['qualifier_findings'] if f['qualifier'] == qualifier for k in fields]
    for capability, statuses in governed.items():
        if capability != 'counter-evidence' and scope[capability] == 'evaluated' and 'not-evaluated' in statuses:
            raise MappingInvalid('evaluated capability governs not-evaluated assessment')
    # Core-02 single-role agreement applies even to unasserted roles.
    for capability in tuple(b + '-support' for b in BASES) + ('provenance-support',):
        statuses = governed[capability]
        if statuses and scope[capability] == 'not-evaluated' and 'not-evaluated' not in statuses:
            raise MappingInvalid('single-role capability contradicts present aggregate')
    if scope['boundary-grounding'] == 'not-evaluated' and 'not-evaluated' not in governed['boundary-grounding']:
        raise MappingInvalid('required boundary role lacks an unevaluated status')
    asserted = input['asserted_claim']
    base = next((f for f in input['base_findings'] if f['base'] == asserted['base']), None)
    required_roles = [(asserted['base'] + '-support', base)]
    for q in asserted['qualifiers']:
        found = next((f for f in input['qualifier_findings'] if f['qualifier'] == q and f['qualified_base'] == asserted['base']), None)
        required_roles.append(('provenance-support' if q == 'PROV' else 'independent-verification', found))
    for capability, aggregate in required_roles:
        if scope[capability] == 'not-evaluated' and (
            aggregate is None or (capability != 'independent-verification' and
                                  'not-evaluated' not in governed[capability])
        ):
            raise MappingInvalid('required unevaluated role missing its unevaluated aggregate')
    # IV is one capability spanning four independently qualified bases. An
    # unevaluated different-base assessment may be unrepresented when unrelated
    # to the assertion (C12). A present passing exact IV aggregate remains passing;
    # the global summary must not rewrite it or manufacture a claim-specific gap.
    # Target-binding spans all findings: an unperformed unrelated binding does
    # not retroactively change a passing binding for the asserted role.
    # Its unevaluated fields are represented on each actual supplied aggregate.
    for capability in ('authenticity', 'composition'):
        marked = any(g.get('current_scope_capability') == capability for g in input['profile_evaluation_gaps'])
        if (scope[capability] == 'not-evaluated') != marked:
            raise MappingInvalid('external capability marker presence mismatch')


def _canonical(input):
    """Copy the logical input, normalizing only collection serialization order."""
    value = deepcopy(input)
    value['asserted_claim']['qualifiers'] = _set(value['asserted_claim']['qualifiers'])
    value['evaluation_context']['profile_identifiers'] = _set(value['evaluation_context']['profile_identifiers'])
    for f in [value['boundary_finding']] + value['base_findings'] + value['qualifier_findings']:
        for field in ('basis_refs', 'reasons', 'limitations'):
            f[field] = _set(f[field])
    for r in value['recorder_relations']:
        for field in ('basis_refs', 'limitations'):
            r[field] = _set(r[field])
    for e in value['counter_evidence'] + value['profile_evaluation_gaps']:
        if e['affected_claims'] != 'all-admissible-claims':
            for claim in e['affected_claims']:
                claim['qualifiers'] = _set(claim['qualifiers'])
            e['affected_claims'] = _set(e['affected_claims'])
        for field in ('basis_refs', 'limitations') + (('reasons',) if 'reasons' in e else ()):
            e[field] = _set(e[field])
    for field in ('base_findings', 'qualifier_findings', 'recorder_relations', 'counter_evidence',
                  'evaluation_scope', 'profile_evaluation_gaps', 'inherited_limitations', 'fatal_conditions'):
        value[field] = _set(value[field])
    return value


def _reject(tokens):
    return {
        'semantics_version': SEMANTICS, 'verdict': 'reject', 'fatal_reasons': _set(tokens),
        'target': None, 'asserted_claim': None, 'asserted_claim_supported': False,
        'support_entries': [], 'supported_claims': [], 'maximal_supported_claims': [],
        'support_relations': [], 'boundary_ceiling': None, 'boundary_grounding': None,
        'recorder_relations': None, 'substantive_reasons': [], 'evaluation_gaps': [],
        'evaluation_gap_entries': [], 'counter_evidence': None, 'inherited_limitations': None,
        'evaluation_context': None, 'evaluation_scope': None,
    }


def _leq(left, right):
    return BASES.index(left['base']) <= BASES.index(right['base']) and set(left['qualifiers']) <= set(right['qualifiers'])


def _relevant(affected, claims):
    return affected == 'all-admissible-claims' or any(_claim_key(c) == _claim_key(a) for c in claims for a in affected)


def appraise(input, profiles=None):
    """Evaluate a complete normalized input; all input rejections are full results.

    Parser/authentication failures before a logical input exists belong to the
    caller. No fallback to finite-world laboratory appraisal is performed.
    """
    if type(input) is not dict or type(input.get('semantics_version')) is not str:
        return _reject(['E_MALFORMED_NORMALIZED_INPUT'])
    try:
        _text(input['semantics_version'])
    except Malformed:
        return _reject(['E_MALFORMED_NORMALIZED_INPUT'])
    if input['semantics_version'] != SEMANTICS:
        return _reject(['E_UNSUPPORTED_SEMANTICS_VERSION'])
    try:
        _shape(input)
    except Malformed:
        return _reject(['E_MALFORMED_NORMALIZED_INPUT'])
    try:
        _cross(input, {} if profiles is None else profiles)
    except MappingInvalid:
        return _reject(['E_PROFILE_MAPPING_INVALID'])
    if input['fatal_conditions']:
        return _reject(input['fatal_conditions'])
    if not _admissible(input['asserted_claim']):
        return _reject(['E_CLAIM_OUT_OF_DOMAIN'])
    v = _canonical(input)
    boundary, asserted = v['boundary_finding'], v['asserted_claim']
    bases = {f['base']: f for f in v['base_findings']}
    quals = {(f['qualifier'], f['qualified_base']): f for f in v['qualifier_findings']}
    usable_boundary = boundary['status'] == boundary['target_binding'] == 'supported'

    def passing(f):
        return f is not None and f['target_binding'] == f['semantic_validation'] == 'supported'

    support, support_entries, used_findings = [], [], []
    for b in BASES:
        f = bases.get(b)
        if not usable_boundary or not passing(f) or BASES.index(b) > BASES.index(boundary['ceiling_base']):
            continue
        available = []
        for q in QUALIFIERS:
            fq = quals.get((q, b))
            if passing(fq) and (q == 'PROV' or fq['independence_validation'] == 'supported'):
                available.append(q)
        for n in range(len(available) + 1):
            for subset in combinations(available, n):
                claim = {'base': b, 'qualifiers': _set(subset)}
                premises = [boundary, f] + [quals[(q, b)] for q in subset]
                support.append(claim)
                used_findings.extend(premises)
                support_entries.append({'claim': claim,
                    'basis_refs': _set(a for p in premises for a in p['basis_refs']),
                    'limitations': _set(a for p in premises for a in p['limitations'])})
    support, support_entries = _set(support), _set(support_entries)
    maximal = [c for c in support if not any(c != d and _leq(c, d) for d in support)]
    supported = asserted in support
    relations = []
    for c in maximal:
        relation = ('equal' if c == asserted else 'support-below-claim' if _leq(c, asserted)
                    else 'support-above-claim' if _leq(asserted, c) else 'incomparable')
        relations.append({'supported_claim': c, 'relation': relation})
    reasons, gaps = [], []
    limits = list(v['inherited_limitations']) + list(boundary['limitations'])
    limits.extend(a for e in support_entries for a in e['limitations'])

    def diagnostic(token, source=None, sources=()):
        premises = ([source] if source is not None else []) + list(sources)
        limits.extend(a for p in premises for a in p['limitations'])
        if token in GAPS:
            gaps.append({'token': token, 'target': v['target'],
                         'evaluation_context_ref': v['evaluation_context']['id'],
                         'affected_claims': [asserted],
                         'basis_refs': _set(a for p in premises for a in p['basis_refs']),
                         'limitations': _set(a for p in premises for a in p['limitations'])})
        else:
            reasons.append(token)

    if boundary['status'] == 'unsupported':
        diagnostic('E_BOUNDARY_NOT_SUPPORTED', boundary)
    if boundary['status'] == 'not-evaluated':
        diagnostic('E_BOUNDARY_NOT_EVALUATED', boundary)
    if boundary['target_binding'] == 'unsupported':
        diagnostic('E_EVIDENCE_NOT_BOUND', boundary)
    if boundary['target_binding'] == 'not-evaluated':
        diagnostic('E_BOUNDARY_NOT_EVALUATED', boundary)
    asserted_base = bases.get(asserted['base'])
    if usable_boundary and asserted_base is not None and BASES.index(asserted['base']) > BASES.index(boundary['ceiling_base']):
        diagnostic('E_BASE_EXCEEDS_BOUNDARY', sources=(boundary, asserted_base))
    if asserted_base is None:
        diagnostic('E_MISSING_REQUIRED_EVIDENCE')
    else:
        if asserted_base['target_binding'] == 'unsupported':
            diagnostic('E_EVIDENCE_NOT_BOUND', asserted_base)
        if 'not-evaluated' in (asserted_base['target_binding'], asserted_base['semantic_validation']):
            diagnostic('E_BASE_NOT_EVALUATED', asserted_base)
        if asserted_base['semantic_validation'] == 'unsupported':
            diagnostic('E_EXACT_CLAIM_NOT_SUPPORTED', asserted_base)
    for q in asserted['qualifiers']:
        f = quals.get((q, asserted['base']))
        if f is None:
            diagnostic('E_MISSING_REQUIRED_EVIDENCE')
            continue
        if f['target_binding'] == 'unsupported':
            diagnostic('E_EVIDENCE_NOT_BOUND', f)
        fields = ('target_binding', 'semantic_validation') + (('independence_validation',) if q == 'IV' else ())
        if any(f[k] == 'not-evaluated' for k in fields):
            diagnostic('E_' + q + '_NOT_EVALUATED', f)
        if f['semantic_validation'] == 'unsupported':
            diagnostic('E_' + q + '_NOT_SUPPORTED', f)
        if q == 'IV' and f['independence_validation'] == 'unsupported':
            diagnostic('E_INDEPENDENCE_NOT_ESTABLISHED', f)
    asserted_roles = [boundary]
    if asserted_base is not None:
        asserted_roles.append(asserted_base)
    asserted_roles.extend(quals[(q, asserted['base'])] for q in asserted['qualifiers'] if (q, asserted['base']) in quals)
    for f in _set(asserted_roles + used_findings):
        reasons.extend(f['reasons'])
        if f['reasons']:
            limits.extend(f['limitations'])
    relevant_claims = [asserted] + support
    for g in v['profile_evaluation_gaps']:
        if _relevant(g['affected_claims'], relevant_claims):
            gaps.append(g)
            limits.extend(g['limitations'])
    blocks = False
    for c in v['counter_evidence']:
        if _relevant(c['affected_claims'], relevant_claims):
            limits.extend(c['limitations'])
        if not _relevant(c['affected_claims'], [asserted]) or c['status'] in ('not-supplied', 'resolved-no-defeat'):
            continue
        blocks = True
        reasons.extend(c['reasons'])
        if c['status'] == 'not-evaluated':
            gaps.append({'token': 'E_COUNTER_EVIDENCE_NOT_EVALUATED',
                         'target': v['target'], 'evaluation_context_ref': v['evaluation_context']['id'],
                         'affected_claims': c['affected_claims'], 'basis_refs': c['basis_refs'],
                         'limitations': c['limitations']})
        elif c['status'] == 'unresolved-material':
            reasons.append('E_COUNTER_EVIDENCE_UNRESOLVED')
        elif c['status'] == 'defeating':
            reasons.append('E_COUNTER_EVIDENCE_DEFEATING')
    return {
        'semantics_version': SEMANTICS, 'verdict': 'accept' if supported and not blocks else 'downgrade',
        'fatal_reasons': [], 'target': v['target'], 'asserted_claim': asserted,
        'asserted_claim_supported': supported, 'support_entries': support_entries,
        'supported_claims': support, 'maximal_supported_claims': _set(maximal),
        'support_relations': _set(relations),
        'boundary_ceiling': boundary['ceiling_base'] if usable_boundary else None,
        'boundary_grounding': boundary['grounding'], 'recorder_relations': v['recorder_relations'],
        'substantive_reasons': _set(reasons), 'evaluation_gaps': _set(g['token'] for g in gaps),
        'evaluation_gap_entries': _set(gaps), 'counter_evidence': v['counter_evidence'],
        'inherited_limitations': _set(limits), 'evaluation_context': v['evaluation_context'],
        'evaluation_scope': v['evaluation_scope'],
    }

