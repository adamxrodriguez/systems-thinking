# Feature Flags + Edge Caching Architecture

## Cache-Aside Pattern

```
Request Flow:
┌─────────┐
│ Client  │
└────┬────┘
     │ GET /flags/{flag_name}
     ▼
┌─────────────────┐
│ FastAPI App     │
└────┬────────────┘
     │
     │ Check Redis Cache
     ▼
┌─────────────────┐
│ Redis Cache     │
│ flag_endpoint:  │
│ {flag_name}     │
└────┬────────────┘
     │
     ├─► Cache Hit ──► Return Cached Response
     │   (Fast: < 10ms)
     │
     └─► Cache Miss ──► Load from Database
                          │
                          ▼
                     ┌────────────┐
                     │ PostgreSQL │
                     │ (Flag Data) │
                     └────┬───────┘
                          │
                          │ Store in Cache
                          ▼
                     ┌────────────┐
                     │ Redis Cache│
                     └────┬───────┘
                          │
                          ▼
                     ┌────────────┐
                     │ Return     │
                     │ Response   │
                     └────────────┘
```

## Cache Layers

```
Multi-Level Caching:
┌─────────────────────┐
│ Request             │
└───────┬─────────────┘
        │
        ▼
┌─────────────────────┐
│ Layer 1:            │
│ Endpoint Cache      │
│ (flag_endpoint:*)   │
│ TTL: 60s            │
└───────┬─────────────┘
        │ Miss
        ▼
┌─────────────────────┐
│ Layer 2:            │
│ Flag Service Cache  │
│ (feature_flag:*)    │
│ TTL: 300s           │
└───────┬─────────────┘
        │ Miss
        ▼
┌─────────────────────┐
│ Layer 3:            │
│ Database            │
│ (PostgreSQL)        │
└─────────────────────┘
```

## Cache Invalidation

```
Flag Update Flow:
┌─────────────────┐
│ Update Flag      │
│ POST /flags/{name}│
│ /update          │
└────┬─────────────┘
     │
     │ 1. Update Database
     ▼
┌─────────────────┐
│ PostgreSQL      │
│ Update Flag     │
└────┬────────────┘
     │
     │ 2. Invalidate Caches
     ▼
┌─────────────────┐
│ Redis Cache       │
│ Delete Keys:      │
│ - feature_flag:*  │
│ - flag_endpoint:* │
│ - flag_check:*    │
└───────────────────┘
     │
     │ 3. Future Requests
     │    Reload from DB
     ▼
┌─────────────────┐
│ Fresh Data      │
│ Cached Again    │
└─────────────────┘
```

## Feature Flag Evaluation

```
Flag Check Logic:
┌──────────────────────┐
│ Get Flag Data        │
│ (from cache or DB)   │
└──────┬───────────────┘
       │
       ├─► Flag Not Found ──► Return False
       │
       ├─► Flag Disabled ──► Return False
       │
       └─► Flag Enabled ──► Check Rollout
                            │
                            ├─► Rollout 100% ──► Return True
                            │
                            └─► Rollout < 100% ──► Calculate User %
                                                      │
                                                      ├─► User % ≤ Rollout ──► True
                                                      │
                                                      └─► User % > Rollout ──► False
```

## Rollout Percentage

```
User-Based Rollout:
┌─────────────────────┐
│ Flag: new_feature    │
│ Rollout: 50%         │
└──────┬───────────────┘
       │
       │ Consistent Hashing
       │ hash(flag_name:user_id) % 100
       │
       ▼
┌─────────────────────┐
│ User 1: hash % 100   │
│ = 23 ──► Enabled    │
│                     │
│ User 2: hash % 100  │
│ = 67 ──► Disabled   │
│                     │
│ User 3: hash % 100  │
│ = 45 ──► Enabled    │
└─────────────────────┘
```

## Redis Data Structures

```
Cache Keys:
┌──────────────────────────────────┐
│ feature_flag:{flag_name}          │
│ - Flag data from database         │
│ - TTL: 300s                      │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ flag_endpoint:{flag}:{user_id}   │
│ - Full endpoint response          │
│ - TTL: 60s                       │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ flag_check:{flag}:{user_id}      │
│ - Boolean result (true/false)     │
│ - TTL: 30s                       │
└──────────────────────────────────┘
```

## Benefits

1. **Performance**: Cached responses return in < 10ms
2. **Scalability**: Reduces database load
3. **Consistency**: Cache invalidation ensures fresh data
4. **Rollout Control**: Gradual feature rollouts
5. **User Experience**: Fast flag checks

