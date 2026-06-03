# PICO — YALex + YAPar Complete Specification & Test Suite

## Overview

**PICO** (*Pico Interpreted Command Operations*) is a minimal expression-oriented language. This document extends the original YALex specification with a full YAPar grammar, covering the complete pipeline from source text to parse tree. Students are expected to implement both a lexer generator (YALex) and a parser generator (YAPar) that together can validate PICO source programs.

---

## Quick Language Reminder

- Variables declared with `let`, assigned with `<-`
- Output via `emit`
- Conditionals: `when` / `otherwise` (with braces)
- Loops: `repeat` / `until`
- Named expressions: `macro`
- Comments: `-- ...` (skipped, no tokens)
- Types: integers, floats, booleans (`true`/`false`), strings

---

## Part 1 — YALex Specification

```
(* pico.yal — YALex specification for the PICO language *)

{
(* Generated lexer for PICO language *)
}

(* ── Character classes ──────────────────────────────── *)

let digit      = ['0'-'9']
let nonzero    = ['1'-'9']
let letter     = ['a'-'z' 'A'-'Z']
let alphanum   = letter | digit | '_'

(* ── Numeric literals ───────────────────────────────── *)

let int_lit    = '0' | nonzero digit*
let float_lit  = int_lit '.' digit+

(* ── String literal ─────────────────────────────────── *)

let str_char   = [^ '"' '\n' '\\'] | '\\' _
let string_lit = '"' str_char* '"'

(* ── Identifiers ────────────────────────────────────── *)

let ident      = letter alphanum*

(* ── Line comment ───────────────────────────────────── *)

let line_cmt   = '-' '-' [^ '\n']* '\n'

(* ══════════════════════════════════════════════════════ *)

rule gettoken =

    [' ' '\t' '\n' '\r']          { return lexbuf }
  | line_cmt                      { return lexbuf }

  | float_lit                     { return FLOAT_LIT }
  | int_lit                       { return INT_LIT }
  | string_lit                    { return STRING_LIT }

  | "true"                        { return BOOL_LIT }
  | "false"                       { return BOOL_LIT }

  | "macro"                       { return KW_MACRO }
  | "emit"                        { return KW_EMIT }
  | "when"                        { return KW_WHEN }
  | "otherwise"                   { return KW_OTHERWISE }
  | "repeat"                      { return KW_REPEAT }
  | "until"                       { return KW_UNTIL }
  | "let"                         { return KW_LET }

  | ident                         { return IDENT }

  | "<-"                          { return ASSIGN }
  | "=="                          { return EQ }
  | "!="                          { return NEQ }
  | "<="                          { return LEQ }
  | ">="                          { return GEQ }
  | "&&"                          { return AND }
  | "||"                          { return OR }

  | '+'                           { return PLUS }
  | '-'                           { return MINUS }
  | '*'                           { return TIMES }
  | '/'                           { return DIV }
  | '<'                           { return LT }
  | '>'                           { return GT }
  | '!'                           { return NOT }

  | '('                           { return LPAREN }
  | ')'                           { return RPAREN }
  | '{'                           { return LBRACE }
  | '}'                           { return RBRACE }
  | ';'                           { return SEMICOLON }
  | ','                           { return COMMA }

  | eof                           { raise( 'End of input' ) }
```

---

## Part 2 — YAPar Grammar Specification

### Token Declarations

```
/* pico.yalp — YAPar specification for the PICO language */

/* ── Token declarations ── */
%token INT_LIT
%token FLOAT_LIT
%token STRING_LIT
%token BOOL_LIT
%token IDENT

%token KW_LET
%token KW_EMIT
%token KW_WHEN
%token KW_OTHERWISE
%token KW_REPEAT
%token KW_UNTIL
%token KW_MACRO

%token ASSIGN
%token PLUS
%token MINUS
%token TIMES
%token DIV
%token EQ
%token NEQ
%token LT
%token GT
%token LEQ
%token GEQ
%token AND
%token OR
%token NOT

%token LPAREN
%token RPAREN
%token LBRACE
%token RBRACE
%token SEMICOLON
%token COMMA

%token WS
IGNORE WS

%%

/* ── Productions ── */

/* Top-level program: one or more statements */
program:
    statement_list
;

statement_list:
    statement_list statement
  | statement
;

/* All valid statement forms */
statement:
    let_stmt
  | emit_stmt
  | when_stmt
  | repeat_stmt
  | macro_def
;

/* Variable declaration: let <ident> <- <expr> ; */
let_stmt:
    KW_LET IDENT ASSIGN expr SEMICOLON
;

/* Output statement: emit <expr> ; */
emit_stmt:
    KW_EMIT expr SEMICOLON
;

/* Conditional: when ( <expr> ) { <stmts> }
               when ( <expr> ) { <stmts> } otherwise { <stmts> } */
when_stmt:
    KW_WHEN LPAREN expr RPAREN LBRACE statement_list RBRACE
  | KW_WHEN LPAREN expr RPAREN LBRACE statement_list RBRACE KW_OTHERWISE LBRACE statement_list RBRACE
;

/* Loop: repeat { <stmts> } until ( <expr> ) ; */
repeat_stmt:
    KW_REPEAT LBRACE statement_list RBRACE KW_UNTIL LPAREN expr RPAREN SEMICOLON
;

/* Macro definition: macro <ident> ( <params> ) { <stmts> }
                     macro <ident> ()            { <stmts> } */
macro_def:
    KW_MACRO IDENT LPAREN param_list RPAREN LBRACE statement_list RBRACE
  | KW_MACRO IDENT LPAREN RPAREN LBRACE statement_list RBRACE
;

/* Parameter list: one or more comma-separated identifiers */
param_list:
    param_list COMMA IDENT
  | IDENT
;

/* ── Expressions (precedence encoded in grammar levels) ── */

/* Level 1 — lowest precedence: logical OR */
expr:
    expr OR expr_and
  | expr_and
;

/* Level 2 — logical AND */
expr_and:
    expr_and AND expr_eq
  | expr_eq
;

/* Level 3 — equality / inequality */
expr_eq:
    expr_eq EQ  expr_cmp
  | expr_eq NEQ expr_cmp
  | expr_cmp
;

/* Level 4 — relational comparisons */
expr_cmp:
    expr_cmp LT  expr_add
  | expr_cmp GT  expr_add
  | expr_cmp LEQ expr_add
  | expr_cmp GEQ expr_add
  | expr_add
;

/* Level 5 — addition and subtraction */
expr_add:
    expr_add PLUS  expr_mul
  | expr_add MINUS expr_mul
  | expr_mul
;

/* Level 6 — multiplication and division */
expr_mul:
    expr_mul TIMES expr_unary
  | expr_mul DIV   expr_unary
  | expr_unary
;

/* Level 7 — unary NOT */
expr_unary:
    NOT expr_unary
  | expr_primary
;

/* Level 8 — primary: literals, identifiers, macro calls, grouped expressions */
expr_primary:
    INT_LIT
  | FLOAT_LIT
  | STRING_LIT
  | BOOL_LIT
  | IDENT
  | IDENT LPAREN arg_list RPAREN
  | IDENT LPAREN RPAREN
  | LPAREN expr RPAREN
;

/* Argument list: one or more comma-separated expressions */
arg_list:
    arg_list COMMA expr
  | expr
;
```

---

### Grammar Notes for Students

1. **Operator precedence is encoded structurally.** There are no `%left`/`%right` directives in YAPar — precedence is expressed by nesting grammar levels. `OR` is at the top (lowest precedence), unary `NOT` is near the bottom (highest among operators).

2. **`when` has two productions.** One with `otherwise` and one without. Both are valid — the parser must accept both forms.

3. **`macro` with and without parameters.** Both `macro f(x) { ... }` and `macro f() { ... }` are syntactically valid. Note that a macro body containing zero statements is not valid — `statement_list` requires at least one statement.

4. **Left recursion in lists.** `statement_list`, `param_list`, and `arg_list` are all left-recursive. This is intentional and standard for bottom-up (SLR/LALR) parsers. Students implementing a top-down parser will need to refactor these.

5. **`program` requires at least one statement.** An empty file is not a valid PICO program syntactically — `statement_list` derives `statement`, which requires a concrete construct.

---

## Part 3 — Test Files That SHOULD Parse Successfully

### ✅ Parse Test 1 — `hello_parse.pico`

```pico
let name <- "world";
emit "Hello, ";
emit name;
```

**Parse trace (simplified):**
```
program
  statement_list
    statement_list
      statement_list
        statement → let_stmt
          KW_LET IDENT("<-") ASSIGN expr(STRING_LIT) SEMICOLON
        statement → emit_stmt
          KW_EMIT expr(STRING_LIT) SEMICOLON
      statement → emit_stmt
        KW_EMIT expr(IDENT) SEMICOLON
```

---

### ✅ Parse Test 2 — `arithmetic_parse.pico`

```pico
let x <- 10;
let y <- 3;
let result <- (x + y) * 2;
emit result;
```

**Parse trace (simplified):**
```
program
  statement_list
    ...
    statement → let_stmt
      KW_LET IDENT ASSIGN
        expr → expr_mul
          expr_primary(LPAREN expr_add(IDENT PLUS IDENT) RPAREN)
          TIMES
          expr_primary(INT_LIT)
      SEMICOLON
    statement → emit_stmt
      KW_EMIT expr(IDENT) SEMICOLON
```

---

### ✅ Parse Test 3 — `conditional_parse.pico`

```pico
let score <- 85;
let passed <- score >= 60;
when (passed) {
    emit "Approved";
} otherwise {
    emit "Failed";
}
```

**Parse trace (simplified):**
```
program
  statement_list
    statement_list
      statement → let_stmt  [ score <- 85 ]
      statement → let_stmt  [ passed <- score >= 60 ]
    statement → when_stmt (with otherwise)
      KW_WHEN LPAREN expr(IDENT) RPAREN
      LBRACE
        statement_list → emit_stmt(STRING_LIT)
      RBRACE
      KW_OTHERWISE
      LBRACE
        statement_list → emit_stmt(STRING_LIT)
      RBRACE
```

---

### ✅ Parse Test 4 — `loop_parse.pico`

```pico
let count <- 5;
repeat {
    emit count;
    let count <- count - 1;
} until (count == 0);
```

**Parse trace (simplified):**
```
program
  statement_list
    statement → let_stmt  [ count <- 5 ]
    statement → repeat_stmt
      KW_REPEAT LBRACE
        statement_list
          statement → emit_stmt(IDENT)
          statement → let_stmt [ count <- expr_add(IDENT MINUS INT_LIT) ]
      RBRACE
      KW_UNTIL LPAREN expr_eq(IDENT EQ INT_LIT) RPAREN SEMICOLON
```

---

### ✅ Parse Test 5 — `macro_with_args_parse.pico`

```pico
macro double(n) {
    let result <- n * 2;
    emit result;
}

let val <- 7;
emit double(val);
```

**Parse trace (simplified):**
```
program
  statement_list
    statement → macro_def
      KW_MACRO IDENT LPAREN
        param_list → IDENT("n")
      RPAREN LBRACE
        statement_list
          let_stmt [ result <- expr_mul(IDENT TIMES INT_LIT) ]
          emit_stmt [ IDENT ]
      RBRACE
    statement → let_stmt [ val <- INT_LIT ]
    statement → emit_stmt
      expr_primary → IDENT LPAREN arg_list(IDENT) RPAREN
```

---

### ✅ Parse Test 6 — `macro_no_args_parse.pico`

```pico
macro greet() {
    emit "Hello!";
}
greet();
```

> **Note:** The bare macro call `greet();` is expressed as an `emit_stmt` wrapping a call `expr_primary`, or as a standalone expression statement. In PICO's grammar as specified, a macro call used as a statement must be wrapped in `emit`. A bare call `greet();` is not a valid top-level statement — see Error Test 5 for the corresponding failure case. This test uses `emit` correctly.

```pico
macro greet() {
    emit "Hello!";
}
emit greet();
```

**Parse trace (simplified):**
```
program
  statement_list
    statement → macro_def
      KW_MACRO IDENT LPAREN RPAREN LBRACE
        statement_list → emit_stmt(STRING_LIT)
      RBRACE
    statement → emit_stmt
      KW_EMIT expr_primary(IDENT LPAREN RPAREN) SEMICOLON
```

---

### ✅ Parse Test 7 — `nested_expr_parse.pico`

```pico
let a <- true;
let b <- false;
let c <- !a || b && a;
emit c;
```

**Parse trace (simplified):**
```
program
  statement_list
    let_stmt [ a <- BOOL_LIT ]
    let_stmt [ b <- BOOL_LIT ]
    let_stmt [ c <-
      expr(OR)
        expr_unary(NOT expr_primary(IDENT))
        expr_and(AND)
          expr_primary(IDENT)
          expr_primary(IDENT)
    ]
    emit_stmt(IDENT)
```

---

### ✅ Parse Test 8 — `multi_param_macro_parse.pico`

```pico
macro add(a, b) {
    let result <- a + b;
    emit result;
}
emit add(3, 4);
```

**Parse trace (simplified):**
```
program
  statement_list
    statement → macro_def
      KW_MACRO IDENT LPAREN
        param_list
          param_list → IDENT("a")
          COMMA IDENT("b")
      RPAREN LBRACE
        statement_list
          let_stmt [ result <- expr_add(IDENT PLUS IDENT) ]
          emit_stmt(IDENT)
      RBRACE
    statement → emit_stmt
      expr_primary → IDENT LPAREN
        arg_list
          arg_list → INT_LIT
          COMMA INT_LIT
      RPAREN
```

---

## Part 4 — Test Files That Should FAIL Parsing

### ❌ Parse Error 1 — `missing_semicolon.pico`

```pico
let x <- 10
emit x;
```

**Expected error:**
```
SYNTAX ERROR at line 2: Expected SEMICOLON after expression in let_stmt, found KW_EMIT
```

**Reason:** `let_stmt` requires `KW_LET IDENT ASSIGN expr SEMICOLON`. The missing `;` after `10` means the parser sees `KW_EMIT` where it expects `SEMICOLON` — a clear reduction failure.

---

### ❌ Parse Error 2 — `missing_assign.pico`

```pico
let x 10;
emit x;
```

**Expected error:**
```
SYNTAX ERROR at line 1: Expected ASSIGN (<-) after IDENT in let_stmt, found INT_LIT
```

**Reason:** `let_stmt` expects `KW_LET IDENT ASSIGN ...`. After `IDENT("x")` the parser expects `ASSIGN` but finds `INT_LIT("10")` — no production matches this sequence.

---

### ❌ Parse Error 3 — `when_without_braces.pico`

```pico
let x <- 1;
when (x)
    emit x;
```

**Expected error:**
```
SYNTAX ERROR at line 3: Expected LBRACE after condition in when_stmt, found KW_EMIT
```

**Reason:** Both `when_stmt` productions require `LBRACE` immediately after the closing `RPAREN` of the condition. Python-style indentation without braces is not valid PICO syntax.

---

### ❌ Parse Error 4 — `otherwise_without_when.pico`

```pico
let x <- 5;
otherwise {
    emit "nope";
}
```

**Expected error:**
```
SYNTAX ERROR at line 2: Unexpected token KW_OTHERWISE — no matching when_stmt context
```

**Reason:** `KW_OTHERWISE` only appears as the second half of a `when_stmt`. A standalone `otherwise` block has no production in the grammar and cannot be reduced to any `statement`.

---

### ❌ Parse Error 5 — `bare_macro_call.pico`

```pico
macro greet() {
    emit "Hi";
}
greet();
```

**Expected error:**
```
SYNTAX ERROR at line 4: IDENT followed by LPAREN is not a valid statement form — macro calls must be wrapped in emit
```

**Reason:** The `statement` production only expands to `let_stmt`, `emit_stmt`, `when_stmt`, `repeat_stmt`, or `macro_def`. A bare `IDENT LPAREN ... RPAREN SEMICOLON` does not match any of these. Macro calls are only valid inside expressions (i.e., as the argument to `emit` or within another expression).

---

### ❌ Parse Error 6 — `empty_macro_body.pico`

```pico
macro doNothing() {
}
emit "done";
```

**Expected error:**
```
SYNTAX ERROR at line 2: Expected at least one statement inside macro body — statement_list requires one or more statements
```

**Reason:** `macro_def` requires `LBRACE statement_list RBRACE`, and `statement_list` must derive at least one `statement`. An empty body `{}` cannot be reduced to `statement_list`.

---

### ❌ Parse Error 7 — `repeat_missing_until.pico`

```pico
let i <- 0;
repeat {
    emit i;
    let i <- i + 1;
}
emit "done";
```

**Expected error:**
```
SYNTAX ERROR at line 6: Expected KW_UNTIL after repeat block RBRACE, found KW_EMIT
```

**Reason:** `repeat_stmt` requires the full form `KW_REPEAT LBRACE statement_list RBRACE KW_UNTIL LPAREN expr RPAREN SEMICOLON`. Closing the brace and moving on without `until (...)` is a syntax error.

---

### ❌ Parse Error 8 — `unbalanced_parens.pico`

```pico
let x <- (3 + 4;
emit x;
```

**Expected error:**
```
SYNTAX ERROR at line 1: Expected RPAREN to close grouped expression, found SEMICOLON
```

**Reason:** `expr_primary → LPAREN expr RPAREN` requires a matching closing parenthesis. The `;` is found before `)`, which breaks the reduction.

---

### ❌ Parse Error 9 — `double_operator.pico`

```pico
let x <- 3 + * 4;
emit x;
```

**Expected error:**
```
SYNTAX ERROR at line 1: Expected expr_primary after PLUS, found TIMES — consecutive operators are not valid
```

**Reason:** `expr_add → expr_add PLUS expr_mul` requires a valid `expr_mul` on the right of `PLUS`. `TIMES` is not a valid start of any `expr_*` production — it is only valid as a binary operator between two subexpressions.

---

## Summary Table

### Valid Programs

| File | Tests |
|---|---|
| `hello_parse.pico` | Basic let + emit, string literals |
| `arithmetic_parse.pico` | Grouped arithmetic expr, operator precedence |
| `conditional_parse.pico` | `when`/`otherwise`, relational expr |
| `loop_parse.pico` | `repeat`/`until`, compound statement list |
| `macro_with_args_parse.pico` | Macro def + call with arguments |
| `macro_no_args_parse.pico` | Zero-param macro def + call via emit |
| `nested_expr_parse.pico` | `!`, `||`, `&&` precedence chain |
| `multi_param_macro_parse.pico` | Multi-param macro, multi-arg call |

### Invalid Programs

| File | Error Type | What It Tests |
|---|---|---|
| `missing_semicolon.pico` | Missing terminal | `;` required at end of `let_stmt` |
| `missing_assign.pico` | Wrong token sequence | `<-` required between IDENT and expr |
| `when_without_braces.pico` | Missing terminal | `{` required after `when (...)` |
| `otherwise_without_when.pico` | No valid production | `otherwise` only valid inside `when_stmt` |
| `bare_macro_call.pico` | No matching statement | Macro call not a valid top-level statement |
| `empty_macro_body.pico` | Empty derivation | `statement_list` requires ≥ 1 statement |
| `repeat_missing_until.pico` | Incomplete production | `until (...)` required after repeat block |
| `unbalanced_parens.pico` | Missing terminal | `RPAREN` required to close grouped expr |
| `double_operator.pico` | Invalid token in position | Binary op cannot follow another binary op |

---

## Notes for Students

1. **The grammar is unambiguous by construction.** Precedence and associativity are encoded in the hierarchy of `expr` → `expr_and` → `expr_eq` → ... → `expr_primary`. You do not need any additional disambiguation rules.

2. **Left recursion is your friend in bottom-up parsing.** All list productions (`statement_list`, `param_list`, `arg_list`) and binary operator productions (`expr_add`, `expr_mul`, etc.) are left-recursive. If you are building an SLR or LALR parser this works directly. If you are building a recursive descent parser you will need to refactor these to right-recursive or iterative forms.

3. **The lexer feeds the parser.** Your YALex-generated lexer must correctly classify tokens before the parser can validate structure. A lexer error on a syntactically valid file should be reported as a lexical error, not a parse error — keep the two error types distinct in your output.

4. **`when` without `otherwise` is valid.** Only the form with `otherwise` is invalid when `otherwise` appears standalone (Error Test 4). A plain `when (cond) { ... }` with no else branch is a perfectly legal PICO statement.

5. **Macro calls are expressions, not statements.** This is the most common conceptual mistake. `greet();` at the top level fails parsing. `emit greet();` succeeds because the call reduces to `expr_primary`, which is a valid `expr`, which is a valid argument to `emit_stmt`.

6. **Error recovery is not required** for this project, but your parser should report the first syntax error clearly (token found, token expected, line number) and stop gracefully rather than crashing.
