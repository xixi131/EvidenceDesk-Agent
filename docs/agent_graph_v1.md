flowchart TD
    A([START]) --> B[classify_intent<br/>判定意图]
    B -->|knowledge 知识| C[retrieve<br/>检索, attempts+1]
    B -->|ambiguous 模糊| D[clarify<br/>反问澄清]
    B -->|unsafe 越权| E[safe_refusal<br/>安全拒答]
    C --> F[grade_retrieval<br/>评估证据够不够]
    F -->|证据够| G[generate_answer<br/>生成带引用回答]
    F -->|不够 且 attempts&lt;2| H[rewrite_query<br/>改写一次查询]
    F -->|不够 且 attempts&ge;2| E
    H --> C
    G --> Z([END])
    D --> Z
    E --> Z
