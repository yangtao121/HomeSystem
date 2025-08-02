# Lobe Chat 知识库API完整指南 - OIDC认证版

## 概述

本文档专门针对使用OIDC认证的Lobe Chat部署，提供完整的JWT Token生成方法和知识库API调用指南。包含从Token生成到API调用的全流程说明，以及详细的代码示例。

**你的Lobe Chat服务器地址**: `http://192.168.5.54:3210`

## 🚀 快速开始

### 第1步：生成JWT Token
```bash
# 创建Token生成脚本
cat > generate-token.js << 'EOF'
import { SignJWT, importJWK } from 'jose';

const jwks = {
  "keys": [{
    "d": "FWviEiVREyjO0QWnXcy1459tkLFWbYhY9p-raxDIwDhzSTHEAePHRv1Mx0Ir7jgWWIVrC5kx0Y7jCZhOQYgTNtqb04gKabSfDCJJoggr1L9Ae5gCyNvDCXxDd9qg3pDZHlG8PXG69Fn2nE5_RmT_J4owi1LwvJS8RDDMownh0cjWsiT-3rsxkDWsyzz9jzwWprpsEpYMwfrIpwb60d7x1N5eCLIS8c-bEZXg5YmqBRf6F-E0xZcpNEu5GwFczM1vVVj5Aeh3CtRzMSBNdmxIe1jnR_CeCEZ8UE4J9vOj92OO973t2sJbWqUorJGbxj5gEq9kasmStFIxPge-Qjjl3w",
    "dp": "6yXi18xcvM345aGe8dKFAfkt7MIuLZDIpA-erBW_0yqeCCrfDHT5qyTEf9OY0qmWpkpHhia10HdaZXDFE1jvtjc6SGNfFlFha9hJ64SVpoMwKcbUFRXVjRPzusm_W3--3-XZpshb-LsdjUv2vI1mDKnxId8fwwTSbHrinGdkS10",
    "dq": "c3B6py8OipjQBVgZgPe-FXEZEpENXBkQnhi2_OWZo9cKyOA5oqiHNyPAhOLp_CIcYmYJMudi6UIF_RtDyL9cFScmnRtvXUOnNcu8zweDAdczDdOt_lbp5VMz5yfwk4uGEvNqR8Fw9Zck9W20--0H2rx24KuiSyc-aCoXtlSBKP0",
    "e": "AQAB",
    "kty": "RSA",
    "n": "4kVBVkVTl7Bd0a8avBv2MZupmxK3cDLFTlFTcCy3-u7rINMjPiZhCOpZbyyMYkhvbZkz2CcCHV1__SrNLl6kDF7tS1C5P6VCHBIlGzQAx9PR0sH7CxnYZnZAFQv5h7bfo11KyrYEFpDnpZpbwjQCvs1bOi0uv7cWLKV8_drxPFYn6_t-wc1riFGhRy8o6vEigI2UzK7zAM9OREJgk2K2hDAs7lpG6DN14PU5gakps00vmRhcG5tUocGNcRchaWFY6UJOm-Rc5MwQcgVKbzjd9uvTQuY6wG3ycS0XEjXnKv2F-WG_SWS8-5Mexc65wFKNfneRrawtqUpFq4pFG6aojQ",
    "p": "_Ha6Npmyp2D-ZXN1aqfD5WL_zGZGVoGMY0-itgw2SfBrtZahfksPz64ztD40poWnk6Kei6WyvwJErnoNFdMjiPUwvTdH6iB-I43Z609LJC31eBlJyTP5AAgOOF8O3Br8FNrS74se-vA7fLBkjbOqlrFbO1xQKVqIvcBVc1jjFR8",
    "q": "5XCa9e-d0VHViKhO00Z4sCLk3v1gE60utyPsWtb7FsiyQPV59X0-L0HhSrKmOpHuLbNKpb5tKZrpLvrl_eGybd2m0A1DmJxtMyeRh1Lauq_2mS7wGaCSDWyXsJd7q-99znqtB97G5fYdAnVf7OLKkYZu39TLdiD2EsrBcYW7wNM",
    "qi": "gbgsibgK-GO-OtE5OvatsAu5vR0tS9_1-oAa5AhG0rheqUPBAzMMR_MbI_pEFco6BpEeMpsN2m1IwouuuMcnwXsDlVoF2th4WVQ4-R2FLaVETgP9Fze6vpnjgrlCsTRaBaoKk72LRYgvOxH2ybdyt_Bl-6CImlQOeKOU560fUxA",
    "use": "sig",
    "kid": "8dc5ac7f74647e9a",
    "alg": "RS256"
  }]
};

async function generateJWTToken(userId, clientId = 'lobe-chat', expiresIn = '24h') {
  const privateKey = await importJWK(jwks.keys[0], 'RS256');
  const now = Math.floor(Date.now() / 1000);
  const hours = parseInt(expiresIn);
  const exp = now + (hours * 3600);
  
  const jwt = await new SignJWT({
    scope: 'read write',
    name: '测试用户',
    email: 'test@example.com'
  })
    .setProtectedHeader({ alg: 'RS256', kid: jwks.keys[0].kid })
    .setIssuedAt(now)
    .setExpirationTime(exp)
    .setSubject(userId)
    .setAudience(clientId)
    .setJti(`jti_${Date.now()}`)
    .sign(privateKey);
  
  return jwt;
}

// 生成Token
const token = await generateJWTToken('user_123456', 'lobe-chat', '24h');
console.log('🎉 JWT Token已生成:');
console.log(token);
console.log('\n📋 复制上面的Token用于API调用');
EOF

# 安装依赖并运行
npm install jose
node generate-token.js
```

### 第2步：测试API连接
```bash
# 将上一步生成的Token替换到下面的命令中
JWT_TOKEN="你生成的JWT_TOKEN"

# 测试获取知识库列表
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: $JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {},
        "path": "knowledgeBase.getKnowledgeBases",
        "type": "query"
      }
    }
  }'
```

### 第3步：创建知识库
```bash
# 创建你的第一个知识库
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: $JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {
          "name": "我的知识库",
          "description": "第一个测试知识库"
        },
        "path": "knowledgeBase.createKnowledgeBase",
        "type": "mutation"
      }
    }
  }'
```

成功后会返回知识库ID，格式如：`{"result":{"data":{"json":"kb_xxxxxxxx"}}}`

## 1. OIDC认证机制与Token生成

### 1.1 环境配置

Lobe Chat需要以下环境变量：

```bash
ENABLE_OIDC=1
OIDC_JWKS_KEY='{"keys":[{"kty":"RSA","use":"sig","kid":"...","alg":"RS256","n":"...","e":"...","d":"..."}]}'
```

**重要说明**：你的OIDC_JWKS_KEY包含完整的RSA密钥对，可以用来：
1. **签发JWT Token**（使用私钥部分）
2. **验证JWT Token**（Lobe Chat服务器自动验证）

### 1.2 JWT Token要求

API调用需要有效的JWT Token，包含以下字段：

```json
{
  "sub": "user_unique_id",          // 必需：用户唯一标识
  "aud": "client_id",               // 必需：客户端ID
  "exp": 1634567890,                // 必需：过期时间戳
  "iat": 1634564290,                // 必需：签发时间戳
  "scope": "read write",            // 可选：权限范围
  "jti": "token_unique_id"          // 可选：Token唯一标识
}
```

### 1.3 认证Header格式

支持两种Header格式：

```bash
# 方式1：自定义Header（推荐）
Oidc-Auth: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

# 方式2：标准OAuth2 Header
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 2. JWT Token生成方法

### 2.1 使用Node.js生成Token

#### 安装依赖
```bash
npm install jose
```

#### 生成脚本 (generate-token.js)
```javascript
import { SignJWT, importJWK } from 'jose';

// 你的JWKS密钥（替换为你的实际密钥）
const jwks = {
  "keys": [{
    "d": "FWviEiVREyjO0QWnXcy1459tkLFWbYhY9p-raxDIwDhzSTHEAePHRv1Mx0Ir7jgWWIVrC5kx0Y7jCZhOQYgTNtqb04gKabSfDCJJoggr1L9Ae5gCyNvDCXxDd9qg3pDZHlG8PXG69Fn2nE5_RmT_J4owi1LwvJS8RDDMownh0cjWsiT-3rsxkDWsyzz9jzwWprpsEpYMwfrIpwb60d7x1N5eCLIS8c-bEZXg5YmqBRf6F-E0xZcpNEu5GwFczM1vVVj5Aeh3CtRzMSBNdmxIe1jnR_CeCEZ8UE4J9vOj92OO973t2sJbWqUorJGbxj5gEq9kasmStFIxPge-Qjjl3w",
    "dp": "6yXi18xcvM345aGe8dKFAfkt7MIuLZDIpA-erBW_0yqeCCrfDHT5qyTEf9OY0qmWpkpHhia10HdaZXDFE1jvtjc6SGNfFlFha9hJ64SVpoMwKcbUFRXVjRPzusm_W3--3-XZpshb-LsdjUv2vI1mDKnxId8fwwTSbHrinGdkS10",
    "dq": "c3B6py8OipjQBVgZgPe-FXEZEpENXBkQnhi2_OWZo9cKyOA5oqiHNyPAhOLp_CIcYmYJMudi6UIF_RtDyL9cFScmnRtvXUOnNcu8zweDAdczDdOt_lbp5VMz5yfwk4uGEvNqR8Fw9Zck9W20--0H2rx24KuiSyc-aCoXtlSBKP0",
    "e": "AQAB",
    "kty": "RSA",
    "n": "4kVBVkVTl7Bd0a8avBv2MZupmxK3cDLFTlFTcCy3-u7rINMjPiZhCOpZbyyMYkhvbZkz2CcCHV1__SrNLl6kDF7tS1C5P6VCHBIlGzQAx9PR0sH7CxnYZnZAFQv5h7bfo11KyrYEFpDnpZpbwjQCvs1bOi0uv7cWLKV8_drxPFYn6_t-wc1riFGhRy8o6vEigI2UzK7zAM9OREJgk2K2hDAs7lpG6DN14PU5gakps00vmRhcG5tUocGNcRchaWFY6UJOm-Rc5MwQcgVKbzjd9uvTQuY6wG3ycS0XEjXnKv2F-WG_SWS8-5Mexc65wFKNfneRrawtqUpFq4pFG6aojQ",
    "p": "_Ha6Npmyp2D-ZXN1aqfD5WL_zGZGVoGMY0-itgw2SfBrtZahfksPz64ztD40poWnk6Kei6WyvwJErnoNFdMjiPUwvTdH6iB-I43Z609LJC31eBlJyTP5AAgOOF8O3Br8FNrS74se-vA7fLBkjbOqlrFbO1xQKVqIvcBVc1jjFR8",
    "q": "5XCa9e-d0VHViKhO00Z4sCLk3v1gE60utyPsWtb7FsiyQPV59X0-L0HhSrKmOpHuLbNKpb5tKZrpLvrl_eGybd2m0A1DmJxtMyeRh1Lauq_2mS7wGaCSDWyXsJd7q-99znqtB97G5fYdAnVf7OLKkYZu39TLdiD2EsrBcYW7wNM",
    "qi": "gbgsibgK-GO-OtE5OvatsAu5vR0tS9_1-oAa5AhG0rheqUPBAzMMR_MbI_pEFco6BpEeMpsN2m1IwouuuMcnwXsDlVoF2th4WVQ4-R2FLaVETgP9Fze6vpnjgrlCsTRaBaoKk72LRYgvOxH2ybdyt_Bl-6CImlQOeKOU560fUxA",
    "use": "sig",
    "kid": "8dc5ac7f74647e9a",
    "alg": "RS256"
  }]
};

async function generateJWTToken(userId, clientId = 'lobe-chat', expiresIn = '24h') {
  try {
    // 导入私钥
    const privateKey = await importJWK(jwks.keys[0], 'RS256');
    
    // 计算过期时间
    const now = Math.floor(Date.now() / 1000);
    const hours = expiresIn.includes('h') ? parseInt(expiresIn) : 24;
    const exp = now + (hours * 3600);
    
    // 创建JWT
    const jwt = await new SignJWT({
      // 可以添加自定义声明
      scope: 'read write',
      name: '用户名称',
      email: 'user@example.com'
    })
      .setProtectedHeader({ 
        alg: 'RS256',
        kid: jwks.keys[0].kid 
      })
      .setIssuedAt(now)
      .setExpirationTime(exp)
      .setSubject(userId)        // 用户ID
      .setAudience(clientId)     // 客户端ID
      .setJti(`jti_${Date.now()}`) // Token唯一ID
      .sign(privateKey);
    
    return jwt;
  } catch (error) {
    console.error('生成JWT失败:', error);
    throw error;
  }
}

// 使用示例
async function main() {
  try {
    // 生成一个测试用户的Token
    const token = await generateJWTToken('user_123456', 'lobe-chat', '24h');
    
    console.log('生成的JWT Token:');
    console.log(token);
    console.log('\\n可以直接在API调用中使用这个Token！');
    
    // 解析Token查看内容（可选）
    const [header, payload, signature] = token.split('.');
    const decodedPayload = JSON.parse(Buffer.from(payload, 'base64url').toString());
    
    console.log('\\nToken内容:');
    console.log(JSON.stringify(decodedPayload, null, 2));
    
  } catch (error) {
    console.error('错误:', error);
  }
}

// 运行
main();
```

#### 运行生成脚本
```bash
node generate-token.js
```

### 2.2 使用Python生成Token

#### 安装依赖
```bash
pip install pyjwt[crypto] cryptography
```

#### Python生成脚本 (generate_token.py)
```python
import jwt
import json
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateNumbers, RSAPublicNumbers
import base64

def base64url_decode(data):
    """Base64URL解码"""
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)
    return base64.urlsafe_b64decode(data)

def jwk_to_private_key(jwk):
    """将JWK格式转换为RSA私钥"""
    
    # 解码JWK中的各个组件
    n = int.from_bytes(base64url_decode(jwk['n']), 'big')
    e = int.from_bytes(base64url_decode(jwk['e']), 'big')
    d = int.from_bytes(base64url_decode(jwk['d']), 'big')
    p = int.from_bytes(base64url_decode(jwk['p']), 'big')
    q = int.from_bytes(base64url_decode(jwk['q']), 'big')
    dp = int.from_bytes(base64url_decode(jwk['dp']), 'big')
    dq = int.from_bytes(base64url_decode(jwk['dq']), 'big')
    qi = int.from_bytes(base64url_decode(jwk['qi']), 'big')
    
    # 构建RSA私钥
    public_numbers = RSAPublicNumbers(e, n)
    private_numbers = RSAPrivateNumbers(p, q, d, dp, dq, qi, public_numbers)
    private_key = private_numbers.private_key()
    
    return private_key

def generate_jwt_token(user_id, client_id='lobe-chat', expires_in_hours=24):
    """生成JWT Token"""
    
    # 你的JWK（替换为你的实际密钥）
    jwk = {
        "d": "FWviEiVREyjO0QWnXcy1459tkLFWbYhY9p-raxDIwDhzSTHEAePHRv1Mx0Ir7jgWWIVrC5kx0Y7jCZhOQYgTNtqb04gKabSfDCJJoggr1L9Ae5gCyNvDCXxDd9qg3pDZHlG8PXG69Fn2nE5_RmT_J4owi1LwvJS8RDDMownh0cjWsiT-3rsxkDWsyzz9jzwWprpsEpYMwfrIpwb60d7x1N5eCLIS8c-bEZXg5YmqBRf6F-E0xZcpNEu5GwFczM1vVVj5Aeh3CtRzMSBNdmxIe1jnR_CeCEZ8UE4J9vOj92OO973t2sJbWqUorJGbxj5gEq9kasmStFIxPge-Qjjl3w",
        "dp": "6yXi18xcvM345aGe8dKFAfkt7MIuLZDIpA-erBW_0yqeCCrfDHT5qyTEf9OY0qmWpkpHhia10HdaZXDFE1jvtjc6SGNfFlFha9hJ64SVpoMwKcbUFRXVjRPzusm_W3--3-XZpshb-LsdjUv2vI1mDKnxId8fwwTSbHrinGdkS10",
        "dq": "c3B6py8OipjQBVgZgPe-FXEZEpENXBkQnhi2_OWZo9cKyOA5oqiHNyPAhOLp_CIcYmYJMudi6UIF_RtDyL9cFScmnRtvXUOnNcu8zweDAdczDdOt_lbp5VMz5yfwk4uGEvNqR8Fw9Zck9W20--0H2rx24KuiSyc-aCoXtlSBKP0",
        "e": "AQAB",
        "kty": "RSA",
        "n": "4kVBVkVTl7Bd0a8avBv2MZupmxK3cDLFTlFTcCy3-u7rINMjPiZhCOpZbyyMYkhvbZkz2CcCHV1__SrNLl6kDF7tS1C5P6VCHBIlGzQAx9PR0sH7CxnYZnZAFQv5h7bfo11KyrYEFpDnpZpbwjQCvs1bOi0uv7cWLKV8_drxPFYn6_t-wc1riFGhRy8o6vEigI2UzK7zAM9OREJgk2K2hDAs7lpG6DN14PU5gakps00vmRhcG5tUocGNcRchaWFY6UJOm-Rc5MwQcgVKbzjd9uvTQuY6wG3ycS0XEjXnKv2F-WG_SWS8-5Mexc65wFKNfneRrawtqUpFq4pFG6aojQ",
        "p": "_Ha6Npmyp2D-ZXN1aqfD5WL_zGZGVoGMY0-itgw2SfBrtZahfksPz64ztD40poWnk6Kei6WyvwJErnoNFdMjiPUwvTdH6iB-I43Z609LJC31eBlJyTP5AAgOOF8O3Br8FNrS74se-vA7fLBkjbOqlrFbO1xQKVqIvcBVc1jjFR8",
        "q": "5XCa9e-d0VHViKhO00Z4sCLk3v1gE60utyPsWtb7FsiyQPV59X0-L0HhSrKmOpHuLbNKpb5tKZrpLvrl_eGybd2m0A1DmJxtMyeRh1Lauq_2mS7wGaCSDWyXsJd7q-99znqtB97G5fYdAnVf7OLKkYZu39TLdiD2EsrBcYW7wNM",
        "qi": "gbgsibgK-GO-OtE5OvatsAu5vR0tS9_1-oAa5AhG0rheqUPBAzMMR_MbI_pEFco6BpEeMpsN2m1IwouuuMcnwXsDlVoF2th4WVQ4-R2FLaVETgP9Fze6vpnjgrlCsTRaBaoKk72LRYgvOxH2ybdyt_Bl-6CImlQOeKOU560fUxA",
        "use": "sig",
        "kid": "8dc5ac7f74647e9a",
        "alg": "RS256"
    }
    
    try:
        # 转换JWK为私钥
        private_key = jwk_to_private_key(jwk)
        
        # 创建JWT载荷
        now = int(time.time())
        exp = now + (expires_in_hours * 3600)
        
        payload = {
            'sub': user_id,                    # 用户ID
            'aud': client_id,                  # 客户端ID
            'iat': now,                        # 签发时间
            'exp': exp,                        # 过期时间
            'jti': f'jti_{int(time.time())}',  # Token唯一ID
            'scope': 'read write',             # 权限范围
            # 可以添加其他自定义字段
            'name': '用户名称',
            'email': 'user@example.com'
        }
        
        # 生成JWT
        token = jwt.encode(
            payload,
            private_key,
            algorithm='RS256',
            headers={'kid': jwk['kid']}
        )
        
        return token
        
    except Exception as e:
        print(f'生成JWT失败: {e}')
        raise

if __name__ == '__main__':
    try:
        # 生成测试Token
        token = generate_jwt_token('user_123456', 'lobe-chat', 24)
        
        print('生成的JWT Token:')
        print(token)
        print('\\n可以直接在API调用中使用这个Token！')
        
        # 解析Token查看内容
        decoded = jwt.decode(token, options={"verify_signature": False})
        print('\\nToken内容:')
        print(json.dumps(decoded, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f'错误: {e}')
```

#### 运行Python脚本
```bash
python generate_token.py
```

### 2.3 Token测试

生成Token后，可以用以下命令测试是否有效：

```bash
# 替换YOUR_GENERATED_TOKEN为实际生成的Token
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_GENERATED_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {},
        "path": "knowledgeBase.getKnowledgeBases",
        "type": "query"
      }
    }
  }'
```

## 3. API基础信息

### 3.1 基础URL
```
POST http://192.168.5.54:3210/trpc/lambda
```

### 3.2 请求格式

TRPC使用特殊的JSON格式，支持批量调用：

```json
{
  "0": {
    "json": {
      "input": { /* 参数 */ },
      "path": "router.method",
      "type": "query|mutation"
    }
  }
}
```

### 3.3 响应格式

```json
[
  {
    "result": {
      "data": {
        "json": { /* 实际数据 */ }
      }
    }
  }
]
```

## 4. 知识库管理API

### 4.1 创建知识库

**端点**: `knowledgeBase.createKnowledgeBase`
**类型**: mutation

**参数**:
```json
{
  "name": "我的知识库",              // 必需：知识库名称
  "description": "知识库描述",      // 可选：描述信息
  "avatar": "https://..."         // 可选：头像URL
}
```

**curl示例**:
```bash
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {
          "name": "我的知识库",
          "description": "这是一个测试知识库"
        },
        "path": "knowledgeBase.createKnowledgeBase",
        "type": "mutation"
      }
    }
  }'
```

**响应示例**:
```json
[
  {
    "result": {
      "data": {
        "json": "kb_xxxxxxxx"
      }
    }
  }
]
```

### 4.2 获取知识库列表

**端点**: `knowledgeBase.getKnowledgeBases`
**类型**: query

**参数**: 无

**curl示例**:
```bash
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {},
        "path": "knowledgeBase.getKnowledgeBases",
        "type": "query"
      }
    }
  }'
```

**响应示例**:
```json
[
  {
    "result": {
      "data": {
        "json": [
          {
            "id": "kb_xxxxxxxx",
            "name": "我的知识库",
            "description": "这是一个测试知识库",
            "avatar": null,
            "isPublic": false,
            "type": null,
            "settings": null,
            "createdAt": "2024-01-01T00:00:00.000Z",
            "updatedAt": "2024-01-01T00:00:00.000Z"
          }
        ]
      }
    }
  }
]
```

### 4.3 获取指定知识库详情

**端点**: `knowledgeBase.getKnowledgeBaseById`
**类型**: query

**参数**:
```json
{
  "id": "kb_xxxxxxxx"
}
```

**curl示例**:
```bash
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {
          "id": "kb_xxxxxxxx"
        },
        "path": "knowledgeBase.getKnowledgeBaseById",
        "type": "query"
      }
    }
  }'
```

### 4.4 添加文件到知识库

**端点**: `knowledgeBase.addFilesToKnowledgeBase`
**类型**: mutation

**参数**:
```json
{
  "knowledgeBaseId": "kb_xxxxxxxx",
  "ids": ["file_id_1", "file_id_2"]
}
```

**curl示例**:
```bash
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {
          "knowledgeBaseId": "kb_xxxxxxxx",
          "ids": ["file_xxxxxxxx"]
        },
        "path": "knowledgeBase.addFilesToKnowledgeBase",
        "type": "mutation"
      }
    }
  }'
```

### 4.5 从知识库移除文件

**端点**: `knowledgeBase.removeFilesFromKnowledgeBase`
**类型**: mutation

**参数**:
```json
{
  "knowledgeBaseId": "kb_xxxxxxxx",
  "ids": ["file_id_1", "file_id_2"]
}
```

### 4.6 删除知识库

**端点**: `knowledgeBase.removeKnowledgeBase`
**类型**: mutation

**参数**:
```json
{
  "id": "kb_xxxxxxxx",
  "removeFiles": true  // 可选：是否同时删除文件
}
```

## 5. 文件管理API

### 5.1 检查文件是否存在

**端点**: `file.checkFileHash`
**类型**: mutation

**参数**:
```json
{
  "hash": "sha256_hash_value"
}
```

**curl示例**:
```bash
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {
          "hash": "abc123def456..."
        },
        "path": "file.checkFileHash",
        "type": "mutation"
      }
    }
  }'
```

**响应示例**:
```json
[
  {
    "result": {
      "data": {
        "json": {
          "isExist": true,
          "url": "https://s3.example.com/files/abc123...",
          "fileType": "application/pdf",
          "size": 1024000,
          "metadata": {}
        }
      }
    }
  }
]
```

### 5.2 创建文件记录

**端点**: `file.createFile`
**类型**: mutation

**参数**:
```json
{
  "name": "document.pdf",
  "fileType": "application/pdf",
  "size": 1024000,
  "hash": "sha256_hash_value",
  "url": "https://s3.example.com/files/...",
  "knowledgeBaseId": "kb_xxxxxxxx",
  "metadata": {}
}
```

**curl示例**:
```bash
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {
          "name": "document.pdf",
          "fileType": "application/pdf",
          "size": 1024000,
          "hash": "abc123def456...",
          "url": "https://s3.example.com/files/abc123...",
          "knowledgeBaseId": "kb_xxxxxxxx"
        },
        "path": "file.createFile",
        "type": "mutation"
      }
    }
  }'
```

### 5.3 获取文件列表

**端点**: `file.getFiles`
**类型**: query

**参数**:
```json
{
  "category": "document",
  "knowledgeBaseId": "kb_xxxxxxxx"
}
```

**curl示例**:
```bash
curl -X POST http://192.168.5.54:3210/trpc/lambda \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: YOUR_JWT_TOKEN" \
  -d '{
    "0": {
      "json": {
        "input": {
          "knowledgeBaseId": "kb_xxxxxxxx"
        },
        "path": "file.getFiles",
        "type": "query"
      }
    }
  }'
```

### 5.4 获取文件详情

**端点**: `file.getFileItemById`
**类型**: query

**参数**:
```json
{
  "id": "file_xxxxxxxx"
}
```

### 5.5 删除文件

**端点**: `file.removeFile`
**类型**: mutation

**参数**:
```json
{
  "id": "file_xxxxxxxx"
}
```

## 6. 完整的文档上传工作流程

### 6.1 步骤概述

1. 计算文件Hash值
2. 检查文件是否已存在
3. 如果不存在，上传文件到存储服务
4. 创建文件记录
5. 添加文件到知识库

### 6.2 完整Shell脚本示例

```bash
#!/bin/bash

# 配置
DOMAIN="http://192.168.5.54:3210"
JWT_TOKEN="YOUR_GENERATED_JWT_TOKEN"
KNOWLEDGE_BASE_ID="kb_xxxxxxxx"
FILE_PATH="/path/to/document.pdf"

# 计算文件Hash
FILE_HASH=$(sha256sum "$FILE_PATH" | cut -d' ' -f1)
echo "文件Hash: $FILE_HASH"

# 1. 检查文件是否存在
echo "检查文件是否已存在..."
CHECK_RESPONSE=$(curl -s -X POST "$DOMAIN/trpc/lambda" \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: $JWT_TOKEN" \
  -d "{
    \"0\": {
      \"json\": {
        \"input\": {
          \"hash\": \"$FILE_HASH\"
        },
        \"path\": \"file.checkFileHash\",
        \"type\": \"mutation\"
      }
    }
  }")

IS_EXIST=$(echo "$CHECK_RESPONSE" | jq -r '.[0].result.data.json.isExist')

if [ "$IS_EXIST" = "true" ]; then
    echo "文件已存在，直接使用现有文件"
    FILE_URL=$(echo "$CHECK_RESPONSE" | jq -r '.[0].result.data.json.url')
else
    echo "文件不存在，需要上传"
    
    # 2. 这里需要实现文件上传到你的存储服务
    # 例如上传到S3、OSS等，获得文件URL
    FILE_URL="https://your-storage.com/files/$FILE_HASH"
    echo "文件已上传到: $FILE_URL"
fi

# 3. 创建文件记录
echo "创建文件记录..."
FILE_SIZE=$(stat -c%s "$FILE_PATH")
FILE_NAME=$(basename "$FILE_PATH")

CREATE_FILE_RESPONSE=$(curl -s -X POST "$DOMAIN/trpc/lambda" \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: $JWT_TOKEN" \
  -d "{
    \"0\": {
      \"json\": {
        \"input\": {
          \"name\": \"$FILE_NAME\",
          \"fileType\": \"application/pdf\",
          \"size\": $FILE_SIZE,
          \"hash\": \"$FILE_HASH\",
          \"url\": \"$FILE_URL\",
          \"knowledgeBaseId\": \"$KNOWLEDGE_BASE_ID\"
        },
        \"path\": \"file.createFile\",
        \"type\": \"mutation\"
      }
    }
  }")

FILE_ID=$(echo "$CREATE_FILE_RESPONSE" | jq -r '.[0].result.data.json.id')
echo "文件ID: $FILE_ID"

# 4. 添加文件到知识库
echo "添加文件到知识库..."
ADD_RESPONSE=$(curl -s -X POST "$DOMAIN/trpc/lambda" \
  -H "Content-Type: application/json" \
  -H "Oidc-Auth: $JWT_TOKEN" \
  -d "{
    \"0\": {
      \"json\": {
        \"input\": {
          \"knowledgeBaseId\": \"$KNOWLEDGE_BASE_ID\",
          \"ids\": [\"$FILE_ID\"]
        },
        \"path\": \"knowledgeBase.addFilesToKnowledgeBase\",
        \"type\": \"mutation\"
      }
    }
  }")

echo "添加结果: $ADD_RESPONSE"
echo "文档上传完成！"
```

## 7. JavaScript SDK示例

```javascript
class LobeChatKnowledgeAPI {
  constructor(baseURL, jwtToken) {
    this.baseURL = baseURL;
    this.jwtToken = jwtToken;
  }

  async call(path, input, type = 'query') {
    const response = await fetch(`${this.baseURL}/trpc/lambda`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Oidc-Auth': this.jwtToken
      },
      body: JSON.stringify({
        "0": {
          json: {
            input,
            path,
            type
          }
        }
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API调用失败: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    
    // 检查是否有错误
    if (data[0]?.error) {
      throw new Error(`API错误: ${data[0].error.json.message}`);
    }
    
    return data[0].result.data.json;
  }

  // 知识库管理
  async createKnowledgeBase(name, description = '', avatar = null) {
    return await this.call('knowledgeBase.createKnowledgeBase', {
      name,
      description,
      avatar
    }, 'mutation');
  }

  async getKnowledgeBases() {
    return await this.call('knowledgeBase.getKnowledgeBases', {});
  }

  async getKnowledgeBaseById(id) {
    return await this.call('knowledgeBase.getKnowledgeBaseById', { id });
  }

  async addFilesToKnowledgeBase(knowledgeBaseId, fileIds) {
    return await this.call('knowledgeBase.addFilesToKnowledgeBase', {
      knowledgeBaseId,
      ids: fileIds
    }, 'mutation');
  }

  async removeFilesFromKnowledgeBase(knowledgeBaseId, fileIds) {
    return await this.call('knowledgeBase.removeFilesFromKnowledgeBase', {
      knowledgeBaseId,
      ids: fileIds
    }, 'mutation');
  }

  async deleteKnowledgeBase(id, removeFiles = false) {
    return await this.call('knowledgeBase.removeKnowledgeBase', {
      id,
      removeFiles
    }, 'mutation');
  }

  // 文件管理
  async checkFileHash(hash) {
    return await this.call('file.checkFileHash', { hash }, 'mutation');
  }

  async createFile(fileData) {
    return await this.call('file.createFile', fileData, 'mutation');
  }

  async getFiles(params = {}) {
    return await this.call('file.getFiles', params);
  }

  async getFileById(id) {
    return await this.call('file.getFileItemById', { id });
  }

  async deleteFile(id) {
    return await this.call('file.removeFile', { id }, 'mutation');
  }

  // 工具方法
  static async calculateFileHash(file) {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }
}

// 使用示例
async function example() {
  const api = new LobeChatKnowledgeAPI('http://192.168.5.54:3210', 'YOUR_JWT_TOKEN');
  
  try {
    // 创建知识库
    const kbId = await api.createKnowledgeBase('我的知识库', '测试知识库');
    console.log('知识库ID:', kbId);
    
    // 获取知识库列表
    const knowledgeBases = await api.getKnowledgeBases();
    console.log('知识库列表:', knowledgeBases);
    
    // 文件上传流程（假设有一个File对象）
    // const fileHash = await LobeChatKnowledgeAPI.calculateFileHash(file);
    // const checkResult = await api.checkFileHash(fileHash);
    
    // if (!checkResult.isExist) {
    //   // 上传文件到存储服务
    //   // const fileUrl = await uploadFileToStorage(file);
    //   
    //   // 创建文件记录
    //   const fileData = {
    //     name: file.name,
    //     fileType: file.type,
    //     size: file.size,
    //     hash: fileHash,
    //     url: fileUrl,
    //     knowledgeBaseId: kbId
    //   };
    //   
    //   const fileResult = await api.createFile(fileData);
    //   await api.addFilesToKnowledgeBase(kbId, [fileResult.id]);
    // }
    
  } catch (error) {
    console.error('操作失败:', error);
  }
}
```

## 8. Python SDK示例

```python
import requests
import json
import hashlib
import os
from typing import Optional, List, Dict, Any

class LobeChatKnowledgeAPI:
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url
        self.jwt_token = jwt_token
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Oidc-Auth': jwt_token
        })

    def call(self, path: str, input_data: Dict[str, Any], call_type: str = 'query') -> Any:
        """调用TRPC API"""
        payload = {
            "0": {
                "json": {
                    "input": input_data,
                    "path": path,
                    "type": call_type
                }
            }
        }
        
        response = self.session.post(
            f"{self.base_url}/trpc/lambda",
            data=json.dumps(payload)
        )
        
        if not response.ok:
            raise Exception(f"API调用失败: {response.status_code} {response.text}")
        
        data = response.json()
        
        # 检查错误
        if data[0].get('error'):
            error_info = data[0]['error']['json']
            raise Exception(f"API错误: {error_info['message']}")
        
        return data[0]['result']['data']['json']

    # 知识库管理
    def create_knowledge_base(self, name: str, description: str = '', avatar: Optional[str] = None) -> str:
        """创建知识库"""
        return self.call('knowledgeBase.createKnowledgeBase', {
            'name': name,
            'description': description,
            'avatar': avatar
        }, 'mutation')

    def get_knowledge_bases(self) -> List[Dict[str, Any]]:
        """获取知识库列表"""
        return self.call('knowledgeBase.getKnowledgeBases', {})

    def get_knowledge_base_by_id(self, kb_id: str) -> Dict[str, Any]:
        """获取指定知识库详情"""
        return self.call('knowledgeBase.getKnowledgeBaseById', {'id': kb_id})

    def add_files_to_knowledge_base(self, knowledge_base_id: str, file_ids: List[str]) -> Any:
        """添加文件到知识库"""
        return self.call('knowledgeBase.addFilesToKnowledgeBase', {
            'knowledgeBaseId': knowledge_base_id,
            'ids': file_ids
        }, 'mutation')

    def remove_files_from_knowledge_base(self, knowledge_base_id: str, file_ids: List[str]) -> Any:
        """从知识库移除文件"""
        return self.call('knowledgeBase.removeFilesFromKnowledgeBase', {
            'knowledgeBaseId': knowledge_base_id,
            'ids': file_ids
        }, 'mutation')

    def delete_knowledge_base(self, kb_id: str, remove_files: bool = False) -> Any:
        """删除知识库"""
        return self.call('knowledgeBase.removeKnowledgeBase', {
            'id': kb_id,
            'removeFiles': remove_files
        }, 'mutation')

    # 文件管理
    def check_file_hash(self, file_hash: str) -> Dict[str, Any]:
        """检查文件是否存在"""
        return self.call('file.checkFileHash', {'hash': file_hash}, 'mutation')

    def create_file(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建文件记录"""
        return self.call('file.createFile', file_data, 'mutation')

    def get_files(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """获取文件列表"""
        return self.call('file.getFiles', params or {})

    def get_file_by_id(self, file_id: str) -> Dict[str, Any]:
        """获取文件详情"""
        return self.call('file.getFileItemById', {'id': file_id})

    def delete_file(self, file_id: str) -> Any:
        """删除文件"""
        return self.call('file.removeFile', {'id': file_id}, 'mutation')

    # 工具方法
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """计算文件SHA256值"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def upload_file_workflow(self, file_path: str, knowledge_base_id: str, 
                           upload_func=None) -> Dict[str, str]:
        """
        完整的文件上传工作流程
        
        Args:
            file_path: 本地文件路径
            knowledge_base_id: 知识库ID
            upload_func: 文件上传函数，返回文件URL
        
        Returns:
            包含文件ID和URL的字典
        """
        # 1. 计算文件Hash
        file_hash = self.calculate_file_hash(file_path)
        print(f"文件Hash: {file_hash}")
        
        # 2. 检查文件是否存在
        check_result = self.check_file_hash(file_hash)
        
        if check_result['isExist']:
            print("文件已存在，使用现有文件")
            file_url = check_result['url']
        else:
            print("文件不存在，需要上传")
            if upload_func:
                file_url = upload_func(file_path, file_hash)
            else:
                # 默认使用文件Hash作为URL（需要根据实际情况修改）
                file_url = f"https://your-storage.com/files/{file_hash}"
                print(f"请手动上传文件到: {file_url}")
        
        # 3. 创建文件记录
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        # 根据文件扩展名判断MIME类型
        file_ext = os.path.splitext(file_name)[1].lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.md': 'text/markdown',
        }
        file_type = mime_types.get(file_ext, 'application/octet-stream')
        
        file_data = {
            'name': file_name,
            'fileType': file_type,
            'size': file_size,
            'hash': file_hash,
            'url': file_url,
            'knowledgeBaseId': knowledge_base_id
        }
        
        file_result = self.create_file(file_data)
        file_id = file_result['id']
        print(f"文件记录已创建，ID: {file_id}")
        
        # 4. 添加文件到知识库
        self.add_files_to_knowledge_base(knowledge_base_id, [file_id])
        print("文件已添加到知识库")
        
        return {
            'file_id': file_id,
            'file_url': file_url,
            'hash': file_hash
        }

# 使用示例
if __name__ == "__main__":
    # 初始化API客户端
    api = LobeChatKnowledgeAPI('http://192.168.5.54:3210', 'YOUR_JWT_TOKEN')
    
    try:
        # 1. 创建知识库
        kb_id = api.create_knowledge_base('我的知识库', '测试知识库')
        print(f'知识库ID: {kb_id}')
        
        # 2. 获取知识库列表
        knowledge_bases = api.get_knowledge_bases()
        print(f'知识库数量: {len(knowledge_bases)}')
        
        # 3. 上传文件到知识库
        file_path = '/path/to/your/document.pdf'
        if os.path.exists(file_path):
            result = api.upload_file_workflow(file_path, kb_id)
            print(f'文件上传完成: {result}')
        else:
            print(f'文件不存在: {file_path}')
        
        # 4. 获取知识库中的文件
        files = api.get_files({'knowledgeBaseId': kb_id})
        print(f'知识库中的文件数量: {len(files)}')
        
    except Exception as e:
        print(f'错误: {e}')
```

## 9. 错误处理

### 9.1 常见错误类型

```json
// 认证失败
{
  "error": {
    "json": {
      "message": "JWT token 验证失败: invalid signature",
      "code": "UNAUTHORIZED",
      "data": {
        "code": "UNAUTHORIZED",
        "httpStatus": 401
      }
    }
  }
}

// 参数错误
{
  "error": {
    "json": {
      "message": "Invalid input",
      "code": "BAD_REQUEST",
      "data": {
        "code": "BAD_REQUEST",
        "httpStatus": 400
      }
    }
  }
}

// 资源不存在
{
  "error": {
    "json": {
      "message": "Knowledge base not found",
      "code": "NOT_FOUND",
      "data": {
        "code": "NOT_FOUND",
        "httpStatus": 404
      }
    }
  }
}
```

### 9.2 错误处理最佳实践

```javascript
async function safeAPICall(apiFunction, ...args) {
  try {
    return await apiFunction(...args);
  } catch (error) {
    console.error(`API调用失败: ${error.message}`);
    
    // 根据错误类型处理
    if (error.message.includes('UNAUTHORIZED')) {
      // Token过期或无效，需要重新生成
      console.log('需要重新生成JWT Token');
      // 重新生成Token的逻辑
    } else if (error.message.includes('NOT_FOUND')) {
      // 资源不存在
      console.log('请求的资源不存在');
    } else if (error.message.includes('BAD_REQUEST')) {
      // 参数错误
      console.log('请检查请求参数');
    }
    
    throw error;
  }
}

// 使用示例
try {
  const result = await safeAPICall(api.getKnowledgeBases);
  console.log('成功:', result);
} catch (error) {
  console.error('最终失败:', error.message);
}
```
