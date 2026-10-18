import {test, expect} from '@playwright/test'
import {MockApi, openBench} from './mock-api.js'

const endpoint = /\/api\/link-jobs\/job1\/factcheck$/
const sse = (events) => events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('')
const report = {
  version:1, module:'factcheck', job_id:'job1', status:'done',
  summary:{total:1, partial:1, exaggerations:1, trusted_sources:1},
  disclaimer:'辅助判断，不构成医疗建议',
  claims:[{id:'c1', claim:'西柚与某些药物相互作用', original_text:'柚子千万别和降压药一起吃',
    timestamp:{start:12,end:15,label:'00:12'}, evidence:{source:'transcript',segment_index:0},
    verdict:'partial',risk:'medium',reason:'需要区分具体药物，不能一概而论。',status:'verified',
    exaggeration:{detected:true,terms:['千万别'],note:'恐吓式表述'},
    sources:[{title:'模拟核查出处',url:'https://pubmed.ncbi.nlm.nih.gov/123',snippet:'用于离线测试的来源摘要',trusted:true,name:'PubMed',kind:'journal'}]}],
}
async function enterChat(page) {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({timeout:30_000})
  await expect(page.locator('.composer__input')).toBeVisible()
}

test('fact-check report streams, displays evidence and reopens from saved report', async ({page}) => {
  await enterChat(page)
  let saved = null
  await page.route(endpoint, async route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({status:saved ? 200 : 404, contentType:'application/json', body:JSON.stringify(saved || {})})
    }
    saved = report
    return route.fulfill({contentType:'text/event-stream',body:sse([
      {type:'factcheck.started'}, {type:'factcheck.claims_extracted',count:1},
      {type:'factcheck.claim.done'}, {type:'factcheck.completed',report},
    ])})
  })
  await openBench(page, '科普')
  const dialog = page.getByRole('region',{name:'科普核查报告'})
  await dialog.getByRole('button',{name:'开始核查',exact:true}).click()
  await expect(dialog.getByText('部分正确',{exact:true}).last()).toBeVisible()
  await expect(dialog.getByRole('link',{name:'模拟核查出处'})).toHaveAttribute('href',report.claims[0].sources[0].url)
  await expect(dialog.getByText('辅助判断，不构成医疗建议',{exact:false})).toBeVisible()
  // the report stays while the sidebar is folded away and shown again
  await page.locator('.bench__handle').click()
  await expect(dialog).toBeHidden()
  await page.locator('.bench__handle').click()
  await expect(dialog.getByText(report.claims[0].reason)).toBeVisible()
})

test('a saved report shows without starting a new check', async ({page}) => {
  await enterChat(page)
  let posted = false
  await page.route(endpoint, route => {
    if (route.request().method() !== 'GET') posted = true
    return route.fulfill({contentType:'application/json', body:JSON.stringify(report)})
  })
  await openBench(page, '科普')
  const region = page.getByRole('region',{name:'科普核查报告'})
  await expect(region.getByText(report.claims[0].reason)).toBeVisible()
  await expect(region.getByRole('button',{name:'重新核查'})).toBeVisible()
  expect(posted).toBe(false)
})

test('server SSE errors are shown to the user', async ({page}) => {
  await enterChat(page)
  await page.route(endpoint, route => route.fulfill(route.request().method()==='GET'
    ? {status:404,body:'{}'}
    : {contentType:'text/event-stream',body:sse([{type:'factcheck.error',code:'no_content',message:'转写尚未完成，请稍后再试'}])}))
  await openBench(page, '科普')
  const dialog=page.getByRole('region',{name:'科普核查报告'})
  await dialog.getByRole('button',{name:'开始核查',exact:true}).click()
  await expect(dialog.getByText('转写尚未完成，请稍后再试')).toBeVisible()
})

test('stopping a request restores the start action', async ({page}) => {
  await enterChat(page)
  let release
  const gate=new Promise(resolve => {release=resolve})
  await page.route(endpoint, async route => {
    if(route.request().method()==='GET') return route.fulfill({status:404,body:'{}'})
    await gate
    await route.fulfill({contentType:'text/event-stream',body:sse([{type:'factcheck.completed',report}])}).catch(()=>{})
  })
  await openBench(page, '科普')
  const dialog=page.getByRole('region',{name:'科普核查报告'})
  await dialog.getByRole('button',{name:'开始核查',exact:true}).click()
  await dialog.getByRole('button',{name:'停止',exact:true}).click()
  await expect(dialog.getByRole('button',{name:'开始核查',exact:true})).toBeVisible()
  release()
})
