import React from 'react'
import { IconArrowLeft } from './Icons'

export default function BackButton({ onClick, destination }) {
  return (
    <button type="button" className="btn btn--ghost btn--back" onClick={onClick} title={`返回${destination}`}>
      <IconArrowLeft /> 返回上一级
    </button>
  )
}
